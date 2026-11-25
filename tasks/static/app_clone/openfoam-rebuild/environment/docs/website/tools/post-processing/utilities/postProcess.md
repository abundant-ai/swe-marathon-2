<!-- https://doc.openfoam.com/2606/tools/post-processing/utilities/postProcess -->

# postProcess

## Overview

The `postProcess` utility evaluates function objects supplied in a
`dictionary` or via the command line.

## Usage

When specified without additional options, the `postProcess` utility
executes all function objects listed in the [controlDict](../../../fundamentals/case-structure/controldict.md)
file for all time directories.

Also, the `-postProcess` option is available to almost all solvers,
and operates similarly to the stand\-alone `postProcess` utility.

Note that the `postProcess` utility does not read any fields by default.
Required fields can be made available using additional command line options,
or inserting a `readFields` function object if using dictionary\-based input.

### Synopsis

```
postProcess [OPTIONS]

```

```
<solver> -postProcess [OPTIONS]

```

#### Examples

##### Custom dictionary

Using a custom dictionary, here using the user\-specified `myDict`:

```
postProcess -dict myDict

```

where `myDict` contains the list of function objects, e.g.

```
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      myDict;
}

functions
{
    // Note: the phi field is required by the CourantNo function object

    readFields1
    {
        type        readFields;
        libs        (fieldFunctionObjects);
        fields      (phi);
    }

    CourantNo1
    {
        type        CourantNo;
        libs        (fieldFunctionObjects);
    }
}

```

##### Command line

Most function objects can be invoked directly without the need to specify
the input dictionary using the `-func` option, e.g. to execute the
[CourantNo](../function-objects/field/CourantNo.md) function object:

```
postProcess -func CourantNo

```

Function objects that require fields can use the `-func` option and insert
the field(s) using a quoted string and parentheses, e.g. to extract velocity
[components](../function-objects/field/components.md):

```
postProcess -func "components(U)"

```

or to [add](../function-objects/field/add.md) fields `T1` and `T2`:

```
postProcess -func "add(T1, T2)"

```

Also, multiple function objects can be invoked simultaneously:

```
postProcess -funcs '(components(U) grad(p))'

```

### Input

#### Arguments

No arguments required.
#### Options

```
-case <dir>       Case directory (instead of current directory)
  -constant         Include 'constant/' dir in the times list
  -decomposeParDict <file>
                    Alternative decomposePar dictionary file
  -dict <file>      Read control dictionary from specified location
  -field <name>     Specify the name of the field to be processed, e.g. U
  -fields <list>    Specify a list of fields to be processed, e.g. '(U T p)'
  -func <name>      Specify the name of the functionObject to execute, e.g. Q
  -funcs <list>     Specify the names of the functionObjects to execute, e.g.
                    '(Q div(U))'
  -latestTime       Select the latest time
  -list             List the available configured functionObjects
  -noZero           Exclude '0/' dir from the times list
  -parallel         Run in parallel
  -profiling        Activate application-level profiling
  -region <name>    Specify mesh region (default: region0)
  -time <ranges>    List of ranges. Eg, ':10,20 40:70 1000:', 'none', etc
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-full        Display full help and exit

```

#### Files

No file input required.

#### Fields

No field input required.

### Output

#### Logs

No log output.

#### Files

No file output.

#### Fields

No field output.

## Further information

Tutorial:

* [cylinder](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/basic/potentialFoam/cylinder)
* [rutlandVortex2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleAdiabaticFoam/rutlandVortex2D)

Source code:

* [postProcess](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/postProcessing/postProcess)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
