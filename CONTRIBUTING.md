# Contributing

Thanks for helping. Wrong chord shapes, new tunings and new instruments are the most useful contributions.

## Reporting a problem

[Open an issue](https://github.com/j-vb/chord_switcher/issues/new/choose) and pick a template. For a wrong chord shape, give the instrument, tuning, chord and frets, and a source if you have one.

## Making a change

1. Fork the repo and create a branch.
2. Set up the app as in [Running from source](README.md#running-from-source), then install the test tools:

   ```sh
   pip install -r requirements-dev.txt
   ```

3. Make your change. To add a tuning or an instrument, see [Adding a tuning or an instrument](README.md#adding-a-tuning-or-an-instrument).
4. Run the tests, and add one when you change how shapes are worked out:

   ```sh
   pytest
   ```

5. Open a pull request that says what changed and why. GitHub runs the tests and builds the app on Windows, macOS and Linux.
