# Step 2 notebook status

The reproducible source of truth for Step 2 is `scripts/profile_data.py` and its JSON output. A Jupyter notebook was not generated because the available project runtime does not currently include `nbformat`, `nbclient`, or Jupyter, and the machine has no registered standalone Python installation.

After installing Python 3.12 and the project requirements, the same evidence can be explored interactively by importing `profile` from `scripts.profile_data`. This avoids committing an unexecuted notebook that could be mistaken for validated evidence.

