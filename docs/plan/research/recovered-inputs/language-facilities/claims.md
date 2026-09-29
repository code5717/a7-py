# Source claims, verbatim (supplied by the user 2026-09-18, third batch)

Grouped by the source they appear to come from; the grouping is this session's
INFERENCE, the text is the user's.

## A. Liveness, conditions, and visual representation

1. "Liveness & Continuous Debugging: Debugging is not something you do after a crash; writing code is debugging an already-running runtime."

2. "Condition Systems over Exceptions: Taking inspiration from Common Lisp, where runtime errors don't unwind the stack and crash the program. Instead, they pause execution in-place, allowing you to recompile the broken function or supply a fix and resume without losing memory state."

3. "Leveraging the Visual Cortex: Moving away from 80-column ASCII text toward embedded visual representations, live data probes, and structural editing."

## B. The loop-editing runtime (Handmade Hero shape)

4. "Contiguous State Memory Block: The platform layer allocates a single, fixed-size contiguous virtual memory block (game_memory) that stores the entire game state (entities, animations, variables). The game logic DLL owns zero static global variables."

5. "Live DLL Swapping: When the code is recompiled, the platform layer unloads the old DLL, loads the new one, and passes the exact same game_memory pointer back in. The state continues unaffected."

6. "Input & State Loop Recording: You hit a hotkey to record player input and freeze a snapshot of memory. Hitting the hotkey again loops that 5-second window: it restores the memory block and replays the recorded gamepad inputs over and over. You can modify the jump physics code while your character repeatedly executes the recorded jump on screen."

## C. Programs as structure, not text

7. "Moving Past ASCII Sequential Files: Why code should be represented as trees, relational graphs, and dynamic constraints rather than sequential lists of text instructions."

8. "Direct Manipulation & Constraint-Based Systems: Defining logic through invariants and spatial relationships (like Sutherland's Sketchpad) rather than procedural loops."

## D. Compile-time execution and layout control

9. "Arbitrary Compile-Time Code Execution (#run): Anything the language can do at runtime can be executed during compilation. The compiler can run tests, fetch assets, or generate lookup tables before emitting bytecode or machine code."

10. "Hot Code Modification: Demonstrating live swapping of function pointers, shaders, and collision geometry in an active Sokoban game without resetting entities."

11. "First-Class Memory Layout Modifiers (SOA vs. AOS): Changing a data structure from Array of Structures to Structure of Arrays with a single keyword, completely altering cache locality and memory layouts without rewriting algorithms."

## E. Objects that decide how they are seen

12. "The Core Concept: When you inspect an object in the debugger (like a network packet, a color gradient, an AST node, or a game entity), it shouldn't show a raw dump of memory bytes. The object itself should define how it wants to be visualized."

13. "Contextual Object Inspectors: An entity struct can define a 2D canvas view, a state-machine graph view, and a raw memory view in just a few lines of code."

14. "Executable Notebooks Blended with Living Runtimes: Combining dynamic document workflows with live compilation pipelines so documentation and running code are never separate."

## F. The live console target (Naughty Dog shape)

15. "The Socket Listener: A live Lisp REPL ran on an SGI workstation connected via Ethernet directly to the PlayStation 2. Developers could redefine a monster's AI behavior, recompile it into raw MIPS assembly, and inject it into the console's memory while the game was running at 60 FPS on the television."

16. "Custom Hardware-Aligned Object System: Automatic memory layout alignment tailored specifically to the PS2's scratchpad RAM and dual vector units (VU0/VU1), proving that high-level live environments can simultaneously be low-level bare-metal systems."
