# Create or open a project

This page shows how to start a project of your own, open an existing one, or explore a ready-made example.

## Open a ready-made example

1. Start the application: `rvs-studio`.
2. **File > Open Example…**, pick a folder and choose *Minimal* (10 items) or *Small satellite* (339 items, with seven planted defects).
3. RVS creates the example in a new sub-folder (`rvs-example-minimal` or `rvs-example-satellite`) and opens it. It never uses a folder that already holds something else.

The same two projects are in the repository under [`examples/`](../../examples/README.md) if you prefer the command line.

## Start a new project from a template

In the application: **File > New Project…** (Ctrl+Alt+N). Give a folder and a name and choose a template:

| Template | You get |
|---|---|
| *Minimal* | system requirements, one subsystem, a verification plan |
| *Small satellite* | mission and system requirements, seven subsystems (EPS, OBC, AOCS, TT&C, structure, thermal, payload), a verification plan |
| *Software product* | system requirements, software requirements, interface requirements, a test specification |

Leave *Keep this project under Git version control* ticked if you want baselines later.

On the command line:

```
rvs init my-project --name "My project" --template satellite --git
```

`--name` is required. `--git` is optional. `rvs init --list-templates` lists the templates. `rvs init` refuses a folder that is not empty and a folder inside another RVS project.

A new project has no items yet. `rvs validate` then prints `INFO DOORSTOP-EMPTY-DOCUMENT` for each empty document: that is normal.

## Open an existing project

**File > Open Project…** (Ctrl+O) and choose the folder that contains `rvs-project.yaml`. **File > Open Recent** lists the last eight. If you choose a folder that is not a project, RVS says so and your previous project stays open.

On the command line every command takes the project folder as its first argument: `rvs validate my-project`.

## Add a document to an existing project

There is no command for this yet. Create the folder, copy a `.doorstop.yml` from a similar document, change its prefix and parent, and add the document to `rvs-project.yaml`. The steps are in the [guide, section 7](../guide/02-guided-walkthrough.md#7-retire-an-item-or-add-a-document).

Next: [Write and edit requirements](02-write-and-edit-requirements.md) · [Project files](10-project-files.md) · [Troubleshooting](../troubleshooting.md)
