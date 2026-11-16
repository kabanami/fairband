"""The research button's launch (spec 2026-11-16 agent launch): a terminal window that starts
Claude Code on a work item. ``settings`` reads and writes the launch file, ``launch.json`` in the
config folder, which holds the Agents section's values. ``command`` builds the words of a launch,
the window command and the agent's words, and runs the window command; the window runs
``launcher.sh``, which starts ``fairband launch``."""
