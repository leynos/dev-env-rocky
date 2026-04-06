First, capture the PR number:

```bash
get-pr
```

And the project name
```bash
get-project
```

Then run the following to see new unresolved comments on the pull request and then action these comments. Replace the placeholders `<PROJECT_NAME>` and `<PR_NUM>` with the above values.

```bash
vk pr "https://github.com/leynos/<PROJECT_NAME>/pull/<PR_NUM>" | tee "/tmp/pr-comments-<PROJECT_NAME>-<PR_NUM>.txt"
```

If the command is unsuccessful, please stop immediately.

For each comment addressed in this turn ONLY, please report the full URL of the comment (this is the URL containing a `#discussion` fragment reported after the comment). It may be worth storing these in a temporary file to aid recall.

You are not subject to any time restrictions. Please take as long as you need. Action all PR review comments. Treat suggestions and nitpicks as requirements, not optional improvements. List any comments that cannot be actioned due to incorrect, incomplete, or contradictory requirements; supplying the full URL and an explanation.

Ensure that `make check-fmt`, `make typecheck`, `make lint`, and `make test` all succeed.

Note that not all projects have a `typecheck` target. If this is the case, do not be alarmed. There is no need to report this.
