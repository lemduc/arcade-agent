# Repository Instructions

## Workflow Decisions

1. **Prefer Updating Existing Pull Requests**: When continuing or consolidating work, prefer updating an existing pull request branch rather than opening a new pull request.

2. **Current Consolidation PR**: Pull Request #4 is the consolidation PR for the current self-dogfooding CI effort.

3. **CI Optimizations**: Focus on simple CI optimizations first, which include:
   - Using pip cache
   - Implementing cancel-in-progress concurrency
   - Utilizing paths-ignore options

4. **Future Updates**: Proactively update these repository instructions when important workflow or process decisions are made during future agent sessions.