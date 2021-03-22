# First Year Value (FYV) $NR

Repository for EDA & developing a model to estimate the first-year-value (in ~net~ gross revenue) for an account (per SFDC).

---

## Getting Setup

### Workflow

Working through code via Jupyter Notebooks is never the preferred pattern for collaboration, which is why the notebook
should be very code-light, i.e., most of the code is abstracted away into easily diff-able `.py` files. These files should be organized into *modules* that can be easily imported into the notebook and will provide a forcing function for you to think critically about how to write your code in the best way possible. Again, this is prescribed specifically for bigger, more "data science-y" projects that need to be prototyped and then productionized in someway rather than one-off analyses.

In order to avoid messy merge conflicts, we use `nbstripout` to strip `.ipynb` files of outputs and execution order
info. If you've installed `nbstripout` correctly, this will automatically happen when you diff notebooks using `git
diff` and when you stage a notebook for a commit.

Note that this is merely one approach; there are other valid workflows that might better suit your needs, such as using something like `jupytext` or developing natively in a `*.py` file, but using an IDE like Spyder, VS Code, or PyCharm to run code in blocks à la JupyterLab or Jupyter Notebook.

A simple workflow would involve:

0. Creating and working off of your own branch.
1. Develop working code in the notebook or create `.py` file to serve as module to be imported into notebook for developing and testing.
2. Move code to `.py` file once satisfied with output and refactor notebook code (if doing the former). These two steps should be done iteratively and involve putting most of the code into functions that can be reused!
3. Commit. Only do this if you've already cleared your notebooks' outputs or if you've properly installed and configured `nbstripout`. If you've done everything correctly, running `$ git check-attr -a -- <path>/foo.ipynb` will yield:

```bash
foo.ipynb: diff: ipynb
foo.ipynb: filter: nbstripout
```

4. (Rinse and repeat as needed; small and frequent commits)
5. Merge from `origin/master` and resolve merge conflicts, if any.
6. Open PR (or merge your local branch directly with `master` and push to remote `master`).

### Requirements

This project uses Python 3.7 and `pipenv` is assumed to be the environment management tool of choice.

> See the `Pipfile` for the required dependencies. Always install from Pipfile.lock (`pipenv sync`) to ensure a deterministic build of you dependencies!

Additionally, custom filters have been added via `nbstripout` to ensure that committed notebooks' outputs and execution
orders are cleared from the file before being committed. (This can also be manually achieved either using `nbstripout
<file>.ipynb` or clearing the cell contents in the Jupyter GUI.

For diffing (and potentially merging) notebooks, we use `nbdime`. See the documentation linked below.

### Installation

_The following assumes that the requirements have been met._

1. Clone this repo and navigate to the parent folder for this project if you haven't done so already.
2. Assuming you already have Python 3.7 and `pipenv` installed (e.g., `brew install pipenv`), run `pipenv install`
to ensure that the dev packages are also installed. (Note, the only dev packages _required_ are `nbdime` and
`nbstripout`; see below).
3. Set up `nbdime` and `nbstripout`. It will have already been installed to your virtual environment in Step 2, but
there are commands that you will have to run (either by `pipenv shell` or `pipenv run <command>`) to complete the set
up:

```bash
# Enter the virtual environment
pipenv shell

# Install dev package settings
nbstripout --install
nbdime extensions --enable
```

4. Spend some time understanding what these two packages do! It will be important that you know how these work and why
we use them (see the **Workflow** section below).

    - `nbdime` documentation can be found [here](https://nbdime.readthedocs.io/en/stable/installing.html).
    - `nbstripout` documentation can be found [here](https://github.com/kynan/nbstripout).

5. Optionally, if you would like `git` to use `nbdime` for diffing and merging notebooks (should you *need* to) by default, check out the documentation (here)[https://nbdime.readthedocs.io/en/stable/vcs.html] to set that up.
