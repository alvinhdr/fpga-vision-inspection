# LEARNING — glossary and interview Q&A

Every new concept goes here (plain English). Add one interview question with a short answer per module.

## Glossary
- **Pass-through**: the video goes into the FPGA and out again unchanged (or with small drawings on top). It is the base that every later feature is built on.
- **Frame buffer**: memory that stores a whole picture. We do not use one. Pixels are processed while they stream past, so the delay is only a few clock cycles (nanoseconds), not a whole frame (16.7 ms).
- **Reuse**: copying proven modules from an older project (HDMI input/output, clock-crossing blocks). Normal in industry, and it lets us spend board time on new work. Each reused file keeps its header and says where it came from.
- **EDID**: a small data block that tells the laptop which video modes the screen accepts. Ours lists only 1280x720@60 so Windows does not choose 1080p (too fast for this chip).
- **AXI-Lite stub**: a placeholder bus slave that answers every read with an ID, so the ARM cannot hang while the real registers do not exist yet.

## Interview Q&A
- **M0 - Why reuse the HDMI blocks from your last project?** Because they were already verified on the board with timing met. Reusing them means any new problem must come from the new code, which makes debugging much faster.

## M1 - capture and lighting
- **Threshold**: a gray level T that splits "part" from "background". Here the part is brighter than the black mat, so a pixel is "part" if gray > T.
- **Exposure lock**: the phone camera normally changes its brightness by itself (auto exposure). That moves the gray levels, so a fixed threshold stops working. We lock it, or we compute the threshold per frame (Otsu).
- **Otsu threshold**: a method that looks at the histogram (how many pixels have each gray level) and picks the T that best separates two groups (dark mat, bright part). Our own frames show why it is needed: the same mat was gray 18 in one session and gray 50 in another.
- **Good / bad parts**: a PASS/FAIL system must be tested with parts it should accept and parts it should reject, otherwise "always PASS" would look perfect.
- **Interview Q&A (M1)**: *Why a black background with bright metal parts?* High contrast makes the threshold easy and robust: the part is far above the background even with soft edges. *Why record data before building the hardware?* The same real frames are used to design the maths, to test the RTL bit-exactly, and to measure accuracy later, even after the board is returned.

## M2 - image moments and the golden model
- **Image moments**: sums over the part pixels. `A` = how many pixels (area). `SX/A, SY/A` = the average position (centre). The second moments (`SXX, SYY, SXY`) say how spread out the pixels are and in which direction: from them we get the angle and the length/width.
- **Why sums suit hardware**: a sum can be updated one pixel at a time (add, never look back), so it needs no frame buffer. Divisions and square roots are done once per frame by the ARM.
- **Equivalent rectangle**: a solid rectangle of n x m pixels has length = sqrt(12*l1 + 1) = n exactly. We use that formula for every part; for a bolt it is a very repeatable "equivalent length".
- **Golden model**: an exact integer Python version of what the hardware computes. The hardware must give the same bits. OpenCV is used as a second, independent opinion on the golden model.
- **Mutation test**: break the model on purpose (wrong filter rule, off-by-one) and check that the test fails. A test that cannot fail proves nothing.
- **Outliers**: one speck far away changes the second moments a lot (a distance squared). That is why we filter, check the box ratio (NOISY), and keep the mat clean.
- **Median and MAD**: the middle value and the typical distance from it. Unlike mean and std, a few bad frames hardly change them.
- **Interview Q&A (M2)**: *Why compute moments in the FPGA but the angle on the ARM?* The FPGA does 55 million pixels per second, so per-pixel work must be simple multiply-adds (DSP48 blocks). The angle needs atan2 and square roots, but only once per frame (60 per second), which is trivial for the ARM. *How do you know your accumulator cannot overflow?* The widths are computed for the worst case (every pixel of the full frame set) and the golden model asserts them on every frame.

## M3+M4 - the hardware measurement core
- **Streaming pipeline**: the pixel goes through several register stages (threshold, filter, multiply, add), one stage per clock. Every clock a new pixel enters, so 74.25 million pixels per second are processed, with only a few clocks of delay.
- **Line buffer**: a small memory that remembers the last two rows (only 2 bits per column here). The 3x3 filter needs the pixels above, and that is all it needs, so no frame buffer.
- **Pad column / flush row**: extra "zero" pixels that the hardware generates itself at the right edge and below the window, so the filter can finish the edge pixels without waiting for more video.
- **DSP48**: a hard multiplier block in the FPGA. u*u, v*v and u*v use 3 of them.
- **Double buffering (two banks)**: the hardware writes the next result into one bank while the ARM reads the other. The ARM never sees a half-written result.
- **Clock domain crossing (CDC)**: moving data between two clocks that are not related (74.25 MHz video, 100 MHz ARM bus). Single bits use 2 flip-flops; groups of bits use a request/acknowledge handshake or "quasi-static" data that is only read while it cannot change. List: docs/CDC.md.
- **Code review finding (real)**: the first bank pointer was a counter on the ARM side; after an ARM-side reset during video it could point to the older bank. Fix: compute the pointer from the synchronized toggle itself, so it has no memory that can get out of step. Lesson: state that copies other state can drift; derive it instead.
- **Interview Q&A (M4)**: *How do you hand a 230-bit result from the video clock to the ARM clock safely?* Two banks: the video side writes one and then flips a toggle bit; the ARM side synchronizes only that one bit with two flip-flops and reads the other bank, which cannot change for a whole frame. The ARM also checks a frame counter before and after reading. *How did you verify the hardware?* The same real camera frames go through the RTL in simulation and through an integer Python model; every sum must be equal bit for bit, plus edge cases (1x1 window, full frame, settings changing exactly at the frame start) and synthetic frames that reach the maximum values.

## M5 / evidence / viewer / AI - what to remember
- **Calibration**: millimetres = pixels x (mm per pixel). The mm per pixel comes from a reference of known size in the same picture, at the same distance. A ruler in the picture is the simplest reference; a thick ruler sits above the surface, so its scale is slightly too large (we corrected by 1.8 %).
- **Median of the last N values**: robust against single bad frames (a bright speck). Important detail: skip bad frames, do not reset the history on them (my first version reset and was undecided 75 % of the time).
- **Stale data**: a USB-serial chip keeps old output that a PC-side buffer flush cannot clear. Detect it (jump in the frame number) and drop it, otherwise the previous recording leaks into the next one. Lesson: check the data you analyse, and re-check numbers that look too good (97 % instead of 99.6 % after the fix).
- **In-sample vs out-of-sample**: a rule tuned on the same parts that are later used to test it is not a blind test. Say so in the results.
- **Leave-one-group-out validation**: hold out a whole recording (not single frames), because frames of one recording are almost identical copies of each other.
- **One-class (novelty) model**: trained on good examples only; anything far from them is "not good". It can reject defects it never saw. Mahalanobis distance = distance measured in units of the data's own spread, including the correlation between features.
- **Interview Q&A**: *You say the AI did not beat the rule. Why keep it in the project?* Because an honest comparison is a result: on this data the features separate the classes so well that a tolerance rule is enough; the model's advantage is no hand-set tolerance. Reporting that is better than claiming a gain that is not there.

## C# for the operator app (first time with C#; compare with C and Python)
- **Project layout** (`pc/`): `InspectionApp` (the WPF window), `InspectionApp.Tests` (xUnit tests). `dotnet build` builds, `dotnet test` runs the tests, like `make` and `pytest`.
- **record**: a small class that only holds data and compares by value (`Measurement` = one result line). Like a C struct with a built-in constructor.
- **Nullable `?`**: `Measurement?` means "a Measurement or nothing". `TryParse` returns `null` for a damaged line, and the compiler forces the caller to handle it. In C this would be a NULL pointer you can forget to check.
- **LINQ**: `lines.Skip(1).Select(...).Where(...).ToList()` is a pipeline over a list, like a Python list comprehension.
- **async / await**: a method can wait (for the serial port, or the replay timer) without freezing the window. `await foreach` reads one measurement at a time from a source; the window stays responsive between them.
- **interface** (`IMeasurementSource`, `ICommandSink`): a promise of what a class can do. The live serial port and the CSV replay both keep the promise, so the window does not care which one it uses; in the tests a fake command sink replaces the serial port.
- **MVVM** in plain words: the **Model** holds the data (`Measurement`), the **View** is the window (`MainWindow.xaml`, only layout), the **ViewModel** (`MainViewModel`) holds everything the window shows and the actions of the buttons. The window *binds* to the ViewModel (`Text="{Binding LengthText}"`), so no code is needed to copy numbers into text boxes, and the logic can be tested without a window.
- **CommunityToolkit.Mvvm**: `[ObservableProperty] private string _verdict;` generates a property `Verdict` that tells the window when it changes; `[RelayCommand]` turns a method into a command a button can call.
- **Culture**: Windows in Indonesian shows `11,3` but the board protocol uses `11.3`. All parsing and sending uses `CultureInfo.InvariantCulture`, and a test checks that the command is `n 11.3 1.6`.
- **Cross-language check**: the C# replay of the real evidence gives the same 22 parts (PASS 14, FAIL 8) as the Python viewer; the test fails if the data file is missing.
- **Interview Q&A**: *Why did you use MVVM instead of writing the logic in the window?* So the logic (parsing, counting parts, yield) is tested without opening a window, and the same view model works for live data and for replay. *How did you test code that needs a serial port?* The serial port sits behind an interface; the tests use a fake that records the commands.
