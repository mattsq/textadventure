# Container Deployment Pipeline

This project ships with a GitHub Actions workflow (`Container Deployment`) that
packages the FastAPI authoring service into a Docker image. The workflow is
suitable for publishing images to GitHub Container Registry (GHCR) and can also
be run manually when you only want to verify a build.

## Triggers

The workflow runs automatically whenever a Git tag that starts with `v` is
pushed (for example, `v1.2.0`). Tag builds log in to GHCR using the
`GITHUB_TOKEN`, build the container defined by the repository `Dockerfile`, and
push versioned tags alongside a `latest` tag for convenience.

You can also launch the workflow manually from the Actions tab. The manual
trigger accepts a `push_image` input so you can choose whether to publish the
image or simply validate that the build succeeds.

## Image Naming

Images are published to `ghcr.io/<owner>/<repository>`. For example, pushing a
`v1.2.0` tag from this repository would produce the following tags:

- `ghcr.io/<owner>/textadventure:v1.2.0`
- `ghcr.io/<owner>/textadventure:latest`
- `ghcr.io/<owner>/textadventure:sha-<commit-sha>`

The workflow relies on `docker/metadata-action` to keep the tag list in sync and
to attach build metadata as OCI labels.

## Manual Runs Without Publishing

When launching the workflow via `workflow_dispatch`, set `push_image` to `false`
to perform a dry run. The workflow will still build the container and generate a
summary in the Actions log, but it will skip authenticating with GHCR and will
not upload any images.

If you would like to test a manual publish, set `push_image` to `true`. The
workflow will authenticate using the `GITHUB_TOKEN` and push tags derived from
the branch or tag that triggered the run.

## Requirements

The workflow depends on a GitHub-hosted runner with Docker available, which is
provided automatically by `ubuntu-latest`. No additional secrets are required
when targeting GHCR because the `GITHUB_TOKEN` is sufficient for pushes to the
current repository's container namespace. If you decide to push to another
registry, update the `REGISTRY` value and provide appropriate credentials via
repository secrets.
