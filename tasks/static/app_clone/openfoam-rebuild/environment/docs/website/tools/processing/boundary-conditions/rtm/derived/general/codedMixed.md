<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/codedMixed -->

# codedMixed

## Description

The `codedMixed` is a mixed\-value boundary condition that
provides an interface to prescribe a user\-coded condition and constructs
a new boundary condition on\-the\-fly which is then used to evaluate.

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
    type                  codedMixed;
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
    refValue        min(10, 0.1*this->db().time().value());
    refGradient     Zero;
    valueFraction   uniform 1;
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `codedMixed` | word | yes | \- |
| `name` | Name of the generated condition | word | yes | \- |
| `code` | OpenFOAM C\+\+ code for patch value assignment | code | yes | \- |
| `codeInclude` | Include files | \- | no | \- |
| `codeOptions` | Compiler line: added to EXE\_INC (Make/options) | \- | no | \- |
| `codeLibs` | Linker line: added to LIB\_LIBS (Make/options) | \- | no | \- |
| `localCode` | Local static functions | \- | no | \- |
| `codeContext` | Additional dictionary context for the code | dict | no | \- |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchFields](https://api.openfoam.com/2606/Foam_mixedFvPatchFields.html)
* [Foam::codedBase](https://api.openfoam.com/2606/Foam_codedBase.html)

## Further information

Tutorial:

* N/A

Source code:

* [codedMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/codedMixed)

API:

* [Foam::codedMixedFvPatchField](https://api.openfoam.com/2606/Foam_codedMixedFvPatchField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
