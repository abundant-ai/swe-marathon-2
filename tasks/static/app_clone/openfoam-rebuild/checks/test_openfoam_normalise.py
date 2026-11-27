"""What the verifier removes from printed output before comparing it, and what it keeps."""

from openfoam_verifier import normalise as N

BANNER = """/*---------------------------------------------------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
\\*---------------------------------------------------------------------------*/"""


def test_banner_date_pid_and_clock_lines_are_removed():
    text = (
        f"{BANNER}\nBuild  : abc\nDate   : Nov 19 2026\nTime   : 22:53:01\nPID    : 4242\n"
        "ExecutionTime = 0.01 s  ClockTime = 0 s\nEnd\n"
    )
    assert N.normalise(text) == ["Build  : abc", "End"]


def test_run_times_in_any_spelling_are_replaced():
    # run times are written both as "in N s" and "in N seconds"
    a = N.normalise("Mapping completed in 0.01 seconds\nMesh refined in = 0.14 s.")
    b = N.normalise("Mapping completed in 3.70 seconds\nMesh refined in = 12.5 s.")
    assert a == b == ["Mapping completed in <time> s", "Mesh refined in <time> s."]


def test_memory_use_is_replaced():
    assert N.normalise(
        "Initial memory 319096 kB\nVTK mesh topology: 0.01 s, 313228 kB"
    ) == ["Initial memory <memory> kB", "VTK mesh topology: <time> s, <memory> kB"]


def test_physical_numbers_are_kept():
    # a number that is a result, not a run time, must still be compared
    assert N.normalise("Courant Number mean: 0.1 max: 0.85") == [
        "Courant Number mean: 0.1 max: 0.85"
    ]
    assert N.normalise("deltaT = 0.005 s") == ["deltaT = 0.005 s"]


def test_error_locations_and_stack_traces_are_removed():
    text = (
        "--> FOAM FATAL ERROR: (openfoam-2606)\nCannot find file\n\n"
        "    From Foam::IFstream::IFstream(const Foam::fileName&)\n"
        "    in file db/IOstreams/Fstreams/IFstream.C at line 123.\n\nFOAM exiting\n"
        "[stack trace]\n=============\n#1  Foam::error::abort() in libOpenFOAM.so\n=============\n"
        "after"
    )
    assert N.normalise(text) == [
        "--> FOAM FATAL ERROR: (openfoam-2606)",
        "Cannot find file",
        "",
        "",
        "FOAM exiting",
        "[stack trace]",
        "after",
    ]



def test_warning_locations_are_removed():
    # a warning gives its source location without the error's closing "."; the path is the build's
    text = (
        "--> FOAM Warning :\n    From void Foam::InteractionLists::buildMap()\n"
        "    in file /src/src/lagrangian/basic/lnInclude/InteractionLists.C at line 1080\n"
        "    Map is empty"
    )
    assert N.normalise(text) == ["--> FOAM Warning :", "    Map is empty"]

def test_case_home_host_and_install_paths_are_replaced():
    rec = N.normalise(
        'Case : /tmp/run/cavity\nHost : node7\nReading "/opt/openfoam/etc/controlDict"\n'
        "Root : /tmp/run\nHome file /home/dev/.OpenFOAM/prefs",
        case_dir="/tmp/run/cavity",
        home="/home/dev",
        host="node7",
        install=(N.RECORDED_INSTALL,),
    )
    sub = N.normalise(
        'Case : /work/run-x/cavity\nHost : sandbox\nReading "/app/rebuild/etc/controlDict"\n'
        "Root : /work/run-x\nHome file /work/run-x/.home/.OpenFOAM/prefs",
        case_dir="/work/run-x/cavity",
        home="/work/run-x/.home",
        host="sandbox",
        install=N.SUBMISSION_INSTALL,
    )
    assert rec == sub
    assert rec[2] == 'Reading "<install>/etc/controlDict"'


def test_dates_in_written_files_are_replaced():
    assert N.strip_dates("// written Wed Nov 19 22:53:01 2026") == "// written <date>"
    assert N.strip_dates("t = 2026-11-19T18:22:33Z") == "t = <date>"
    assert N.strip_dates("value 22.53") == "value 22.53"
