# Dependabot Reference

Source 1: https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file
- Rebase and target-branch (lines 746-750):
  "Dependabot default behavior is to rebase open pull requests when Dependabot detects any changes to a version or security update pull request. Dependabot checks for changes when:
  ...
  * You change the value of `target-branch` in the Dependabot configuration file, see `target-branch`."
- Security updates and default branch (line 900):
  "* Options defined for this `package-ecosystem` no longer apply to security updates because security updates always use the default branch for the repository."

Source 2: https://docs.github.com/en/code-security/dependabot/working-with-dependabot/managing-pull-requests-for-dependency-updates
- @dependabot recreate (line 28):
  "| `@dependabot recreate` | Recreates the pull request, overwriting any edits that have been made to the pull request. |"
