<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/codedFixedValue -->

# codedFixedValue

## Description

The `codedFixedValue` is a fixed\-value boundary condition that
provides an interface to prescribe a user\-coded condition and constructs
a new boundary condition on\-the\-fly (derived from
[fixedValue condition](fixedValue.md))
which is then used to evaluate.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            <type>;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                  codedFixedValue;
    name                  <word>;

    // Optional entries
    codeInclude
    #{
        #include "fvCFD.H"
    #};

    codeOptions
    #{
        -I$(LIB_SRC)/finiteVolume/lnInclude \
        -I$(LIB_SRC)/meshTools/lnInclude
    #};

    codeLibs
    #{
        -lfiniteVolume \
        -lmeshTools
    #};

    localCode
    #{
        // OpenFOAM C++ code
    #};

    codeContext             <dict>;

    // Conditional entries

        // if the 'code' keyword is present
        code
        #{
            // OpenFOAM C++ code
        #};

        // if the 'code' keyword is not present,
        // read the code from a dictionary from 'system/codeDict'
        <patchName>
        {
            code
            #{
                // OpenFOAM C++ code
            #};
        }

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `codedFixedValue` | word | yes | \- |
| `name` | Name of the generated condition | word | yes | \- |
| `code` | OpenFOAM C\+\+ code for patch value assignment | code | yes | \- |
| `codeInclude` | Include files | \- | no | \- |
| `codeOptions` | Compiler line: added to EXE\_INC (Make/options) | \- | no | \- |
| `codeLibs` | Linker line: added to LIB\_LIBS (Make/options) | \- | no | \- |
| `localCode` | Local static functions | \- | no | \- |
| `codeContext` | Additional dictionary context for the code | dict | no | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::codedBase](https://api.openfoam.com/2606/Foam_codedBase.html)

A simple example showing how to ramp the patch values as a function of time

p\=min⁡(10,0\.1t) p \= \\min (10, 0\.1 t)p\=min(10,0\.1t)
is specified in the field file using:

```
<patchName>
{
    type            codedFixedValue;
    value           uniform 0;

    name            rampedFixedValue;

    code
    #{
        const scalar t = this->db().time().value();
        operator==(min(10, 0.1*t));
    #};
}

```

Only basic functionality is offered by default, e.g. access to the mesh
(`Foam::fvMesh`) and time (`Foam::Time`) databases. For more complex conditions
access to additional classes is enabled via the optional `codeInclude` and
`codeOptions` entries, e.g.

```
codeInclude
#{
    #include "fvCFD.H"
#};

codeOptions
#{
    -I$(LIB_SRC)/finiteVolume/lnInclude
#};

```

This is equivalent to the required entries in the `Make/options` file when
building code libraries.

## Further information

Tutorial:

* [pipeCyclic](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/pipeCyclic)

Source code:

* [codedFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/codedFixedValue)

API:

* [Foam::codedFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_codedFixedValueFvPatchField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
