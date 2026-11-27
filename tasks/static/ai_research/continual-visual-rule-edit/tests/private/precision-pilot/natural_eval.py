"""Apply the same prospective deployment protocol to width-28 checkpoints with no row copies."""

from importlib.util import module_from_spec, spec_from_file_location

from natural_data import ROOT, station

path = (
    ROOT / "long_eval.py"
    if (ROOT / "long_eval.py").exists()
    else ROOT.parent / "extended" / "long_eval.py"
)
spec = spec_from_file_location("unexpanded_field_evaluation", path)
core = module_from_spec(spec)
spec.loader.exec_module(core)
core.ROOT = ROOT
core.station = station
simulate = core.simulate
build_inputs = core.build_inputs
score_edits = core.score_edits
run_editor = core.run_editor
reward = core.reward
summary = core.summary
