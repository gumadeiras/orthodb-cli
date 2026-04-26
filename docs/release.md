# Release Notes

Release flow is intentionally small until Homebrew packaging lands.

1. Update `src/orthodb_cli/__init__.py`.
2. Run gates:

   ```bash
   PYTHONPATH=src python3 -m unittest discover -s tests
   python3 -m compileall -q src tests
   ```

3. Tag with `vX.Y.Z`.
4. Push the tag.
5. Download the `dist` artifact from the Release workflow.

Future Homebrew tap work should use the tagged source archive checksum from
GitHub or the built sdist checksum from the workflow artifact.

