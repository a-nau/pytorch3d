# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import importlib
import json
import os
import sys
import unittest
import unittest.mock
from collections import Counter

from common_testing import get_pytorch3d_dir


# This file groups together tests which look at the code without running it.
in_conda_build = os.environ.get("CONDA_BUILD_STATE", "") == "TEST"
in_re_worker = os.environ.get("INSIDE_RE_WORKER") is not None


class TestBuild(unittest.TestCase):
    def test_name_clash(self):
        # For setup.py, all translation units need distinct names, so we
        # cannot have foo.cu and foo.cpp, even in different directories.
        source_dir = get_pytorch3d_dir() / "pytorch3d"

        stems = []
        for extension in [".cu", ".cpp"]:
            files = source_dir.glob(f"**/*{extension}")
            stems.extend(f.stem for f in files)

        counter = Counter(stems)
        for k, v in counter.items():
            self.assertEqual(v, 1, f"Too many files with stem {k}.")

    @unittest.skipIf(in_re_worker, "In RE worker")
    def test_copyright(self):
        root_dir = get_pytorch3d_dir()

        extensions = ("py", "cu", "cuh", "cpp", "h", "hpp", "sh")

        expect = "Copyright (c) Facebook, Inc. and its affiliates.\n"

        files_missing_copyright_header = []

        for extension in extensions:
            for path in root_dir.glob(f"**/*.{extension}"):
                excluded_files = (
                    "pytorch3d/transforms/external/kornia_angle_axis_to_rotation_matrix.py",
                    "pytorch3d/csrc/pulsar/include/fastermath.h",
                )
                if in_conda_build:
                    excluded_files += (
                        "run_test.py",
                        "run_test.sh",
                        "conda_test_runner.sh",
                        "conda_test_env_vars.sh",
                    )

                if str(path).endswith(excluded_files):
                    continue
                with open(path) as f:
                    firstline = f.readline()
                    if firstline.startswith(("# -*-", "#!", "/*")):
                        firstline = f.readline()
                    if not firstline.endswith(expect):
                        files_missing_copyright_header.append(str(path))

        if len(files_missing_copyright_header) != 0:
            self.fail("\n".join(files_missing_copyright_header))

    @unittest.skipIf(in_re_worker, "In RE worker")
    def test_valid_ipynbs(self):
        # Check that the ipython notebooks are valid json
        root_dir = get_pytorch3d_dir()
        tutorials_dir = root_dir / "docs" / "tutorials"
        tutorials = sorted(tutorials_dir.glob("*.ipynb"))

        for tutorial in tutorials:
            with open(tutorial) as f:
                json.load(f)

    @unittest.skipIf(in_conda_build or in_re_worker, "In conda build, or RE worker")
    def test_enumerated_ipynbs(self):
        # Check that the tutorials are all referenced in tutorials.json.
        root_dir = get_pytorch3d_dir()
        tutorials_dir = root_dir / "docs" / "tutorials"
        tutorials_on_disk = sorted(i.stem for i in tutorials_dir.glob("*.ipynb"))

        json_file = root_dir / "website" / "tutorials.json"
        with open(json_file) as f:
            cfg_dict = json.load(f)
        listed_in_json = []
        for section in cfg_dict.values():
            listed_in_json.extend(item["id"] for item in section)

        self.assertListEqual(sorted(listed_in_json), tutorials_on_disk)

    @unittest.skipIf(in_conda_build or in_re_worker, "In conda build, or RE worker")
    def test_enumerated_notes(self):
        # Check that the notes are all referenced in sidebars.json.
        root_dir = get_pytorch3d_dir()
        notes_dir = root_dir / "docs" / "notes"
        notes_on_disk = sorted(i.stem for i in notes_dir.glob("*.md"))

        json_file = root_dir / "website" / "sidebars.json"
        with open(json_file) as f:
            cfg_dict = json.load(f)
        listed_in_json = []
        for section in cfg_dict["docs"].values():
            listed_in_json.extend(section)

        self.assertListEqual(sorted(listed_in_json), notes_on_disk)

    def test_no_import_cycles(self):
        # Check each module of pytorch3d imports cleanly,
        # which may fail if there are import cycles.

        # First check the setup of the test. If any of pytorch3d
        # was already imported the test would be pointless.
        for module in sys.modules:
            self.assertFalse(module.startswith("pytorch3d"), module)

        root_dir = get_pytorch3d_dir() / "pytorch3d"
        for module_file in root_dir.glob("**/*.py"):
            if module_file.stem == "__init__":
                continue
            relative_module = str(module_file.relative_to(root_dir))[:-3]
            module = "pytorch3d." + relative_module.replace("/", ".")
            with self.subTest(name=module):
                with unittest.mock.patch.dict(sys.modules):
                    importlib.import_module(module)
