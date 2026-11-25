<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/ -->

# Function objects

Function objects are OpenFOAM utilities, designed to ease setups and
enhance workflows by generating user\-requested data both during
runtime and post\-processing, typically in the form of logging to the screen,
or text, image and field files.

Function objects eliminate the need to store all runtime generated data,
hence saving considerable resources. Furthermore, function objects are
readily applied to batch\-driven processes, improving reliability by
standardising the sequence of operations and reducing the amount of manual
interaction.

The output of most function objects, e.g. output fields, are
stored on the mesh database to enable retrieval and chaining to other
function objects and applications, e.g. using
[wallShearStress](field/wallShearStress.md) function
object output in a [fieldAverage](field/fieldAverage.md)
function object to produce the `wallShearStressMean` field.

## Usage

Function objects can be executed using two methods:

* at run\-time: via the `functions` sub\-dictionary in the
[controlDict](../../../fundamentals/case-structure/controldict.md) file;
* post\-processing on time directories:
	+ [postProcess](../utilities/postProcess.md) command\-line utility, and
	+ `<application> -postProcess` option available to

```
[solver applications](../../processing/solvers/index.md).

```

### Run\-time

Each function object should be listed inside the `functions` sub\-dictionary of
the [controlDict](../../../fundamentals/case-structure/controldict.md) file as shown in the following example:

```
functions    // sub-dictionary name under the system/controlDict file
{
    <userDefinedSubDictName1>
    {
        // Mandatory entries
        type                <functionObjectTypeName>;
        libs                (<libType>FunctionObjects);

        // Mandatory entries defined in <functionObjectType>
        ...

        // Optional entries defined in <functionObjectType>
        ...

        // Optional (inherited) entries
        region              region0;
        enabled             true;
        log                 true;
        timeStart           0;
        timeEnd             1000;
        executeControl      timeStep;
        executeInterval     1;
        writeControl        timeStep;
        writeInterval       1;
    }

    <userDefinedSubDictName2>
    {
        ...
    }

    ...

    <userDefinedSubDictNameN>
    {
        ...
    }
}

```

where the entries are described below:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name of function object | word | yes | \- |
| libs | Library name containing implementation | word | yes | \- |
| region | Name of region for multi\-region cases | word | no | region0 |
| enabled | Switch to turn function object on/off | bool | no | true |
| log | Switch to write log info to standard output | bool | no | true |
| timeStart | Start time for function object execution | scalar | no | 0 |
| timeEnd | End time for function object execution | scalar | no | inf |
| executeControl | See time controls below | word | no | timeStep |
| executeInterval | Steps/time between execute phases | label | no | 1 |
| writeControl | See time controls below | word | no | timeStep |
| writeInterval | Steps/time between write phases | label | no | 1 |

The sub\-dictionary name `<userDefinedSubDictName>` is chosen by the user,
and is typically used as the name of the output directory for any data
written by the function object.

As the base mandatory entry, the `type` entry defines the type of
function object properties that follow. Function objects are packaged into
separate libraries for flexibility and the `libs` entry is used to specify
which library should be loaded.

### Function object controls

When applied at run\-time, the objects are controlled according to the optional
two time\-based entries:

* `executeControl`: when the object is updated (for updating calculations
or for management tasks),
* `writeControl`: when the object output is written (for writing the calculated
data to disk).

If neither entries are present the object will execute and write every time
step\-\-\-which can create much more data than intended!

Values for these controls take the same type of values as the `writeControl`
entry in the [controlDict](../../../fundamentals/case-structure/controldict.md), with some additions:

| Option | Description |
| --- | --- |
| none | Trigger is disabled |
| timeStep | Trigger every 'Interval' time\-steps, e.g. every x time steps |
| writeTime | Trigger every 'Interval' output times, i.e. alongside standard field output |
| runTime | Trigger every 'Interval' run time period, e.g. every x seconds of calculation time |
| adjustableRunTime | Currently identical to "runTime" |
| clockTime | Trigger every 'Interval' clock time period |
| cpuTime | Trigger every 'Interval' CPU time period |
| onEnd | Trigger on end of simulation run |

For example, to set a
[Courant Number function object](field/CourantNo.md)
to evaluate every 2 time steps and write at every output time:

```
functions
{
    Co1
    {
        type                CourantNo;
        libs                (fieldFunctionObjects);
        executeControl      timeStep;
        executeInterval     2;
        writeControl        writeTime;
    }
}

```

Data derived from function objects are written to the case `postProcessing`
directory or to the time directories, typically in a subdirectory with the same
name as the object, e.g.

```
$FOAM_CASE/postProcessing/<functionObjectName>/<time>/<data>

$FOAM_CASE/<time>/<outField>

```

Many function objects create fields that can be stored for later use. To avoid
potential name clashes in the database, the `useNamePrefix` entry can be used to
prepend the name of the function object to the name of the output field,
e.g. applied to a [fieldAverage](field/fieldAverage.md)
function object, a velocity mean field could be named `fieldAverage1:UMean`.

### Post\-processing on time directories

#### Post\-process utility

The standalone `postProcess` utility executes function objects on disk\-based
data in time directories. For more information, please see:

* [postProcess](../utilities/postProcess.md) utility.

#### Application post\-processing

The `-postProcess` command\-line option is available to all solvers, and operates
similarly to the stand\-alone [postProcess](../utilities/postProcess.md) utility.
For example, having completed a [simpleFoam](../../processing/solvers/rtm/incompressible/simpleFoam.md) calculation,
the following will execute all function objects defined in the
[controlDict](../../../fundamentals/case-structure/controldict.md) file for all time directories:

```
simpleFoam -postProcess

```

which will execute all function objects defined in the
[controlDict](../../../fundamentals/case-structure/controldict.md).

## Options

Function objects are grouped into libraries that perform similar operations
or operate on similar object types:

* [Field](field/index.md)
* [Forces](forces/index.md)
* [Graphics](graphics/index.md)
* [Lagrangian](lagrangian/index.md)
* [Sampling](sampling/index.md)
* [Solvers](solvers/index.md)
* [Utilities](utilities/index.md)

## Further information

Source code:

* [functionObjects](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/db/functionObjects)
* [functionObjects](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects)

API:

* [Source documentation](https://api.openfoam.com/2606/grpFunctionObjects.html)
