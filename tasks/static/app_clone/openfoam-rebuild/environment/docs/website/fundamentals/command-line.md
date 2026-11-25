<!-- https://doc.openfoam.com/2606/fundamentals/command-line -->

# Command line

## Command line interface *user @openfoam:\~$...*

OpenFOAM comprises many applications, primarily designed to be driven by the
*command line*. Whilst sometimes unfamiliar to new users, this interface
provides the most flexible means by which to control the phases of case set\-up,
execution and evaluation of results, and lends itself to automation and
batch\-processing.

## Basic usage

Applications are invoked using commands of the form:

```
<application> [OPTIONS] <arguments>

```

More detailed usage information is available using the *help* option; for
example, when applied to the blockMesh application as:

```
blockMesh -help

```

the following text is presented:

```
blockMesh [OPTIONS]

```

## Navigation

### Useful commands

Moving around the source code and cases is easily performed using standard
linux commands, e.g.

* `ls`: list directory contents
* `cd`: change directory

In addition, several *aliases* are available which provide short cuts to many
OpenFOAM directories. These include:

* `foam`: change to the main OpenFOAM project directory
* `src`: change to the top\-level source directory
* `sol`: change to the top\-level solver directory
* `util`: change to the top\-level utilities directory
* `tut`: change to the top\-level tutorial directory

### Tab completion

Command line tab completion of OpenFOAM applications presents users with
selections that are tailored for the current action. For example, issuing

```
checkMesh <TAB> <TAB>

```

returns the list of available options for the `checkMesh` utility:

```
  -allGeometry      Include all geometry checks
  -allTopology      Include all topology checks
  -case <dir>       Case directory
  -constant         Include constant directory in times list
  -doc              Display documentation in browser
  -help             Display short help and exit
  -latestTime       Select latest time
  -meshQuality      Print mesh quality parameters
  -noFunctionObjects
  -region <name>    Specify region name
  -time <time>      Specify time
  -write-vtk        Write mesh in VTK format
  -writeSets        Write cell sets for failed checks

```

Many options require additional user inputs, identified by `-option <value>`
entries when requesting help via the `-help` option, as shown in the
previous [blockMesh](command-line.md#usage) example.

If using the `-time` option, the completion will limit the options to the list
of available times, e.g. after running the tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/icoFoam/cavity/cavity)

Invoking the following:

```
checkMesh -time <TAB> <TAB>

```

returns:

```
0    0.1  0.2  0.3  0.4  0.5

```

Multi\-region cases are notoriously complex to set\-up and process. The `-region`
option will limit the available options to the list of regions, e.g. applied to
the tutorial:

* [heatExchanger](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionSimpleFoam/heatExchanger)

Invoking the following:

```
checkMesh -region <TAB> <TAB>

```

returns:

```
air     porous

```

### Command line help

Manual pages provide a straightforward interface to access the options
available to all OpenFOAM applications. See the full list of options here:

* [Man pages](../man/index.md)
