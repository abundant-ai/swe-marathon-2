<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/coded -->

# Coded source

The `coded` option provides several hooks that can be implemented in C\+\+ code
to manipulate the system of equations, e.g. by including additional source
terms and modifying the equation matrices.

## Properties

The `coded` option is available to all primitive field types, i.e.

* `scalarCodedSource`: scalar equations
* `vectorCodedSource`: vector equations
* `sphericalTensorCodedSource`: vector equations
* `symmTensorCodedSource`: vector equations
* `tensorCodedSource`: vector equations

It provides hooks to:

* include sources: `codeAddSup`
* constrain values before the equation is solved: `codeSetValue`
* apply corrections after the equation has been solved: `codeCorrect`

## Usage

An example showing how to add a source to the energy equation of the form

Sh\=1V100000sin⁡(200Cx) S\_h \= \\frac{1}{V} 100000 \\sin(200 C\_x)Sh​\=V1​100000sin(200Cx​)
is shown below:

```
codedSource
{
    type            coded;
    selectionMode   all;

    fields          (h);
    name            sourceTime;

    codeAddSup
    #{
        const Time& time = mesh().time();
        const scalarField& V = mesh_.V();
        scalarField& heSource = eqn.source();

        // Start time
        const scalar startTime = 2.0;

        // Retrieve the x component of the cell centres
        const scalarField& cellx = mesh_.C().component(0);

        // Only apply when we have reached the start time
        if (time.value() > startTime)
        {
            // Apply the source
            forAll(cellx, i)
            {
                // cell volume specific source
                heSource[i] += 1e5*sin(200*cellx[i])*V[i];
            };
        }
    #};
}

```

By default the coded option links against the following libraries:

* `finiteVolume`: finite volume machinery
* `meshTools`: mesh tools
* `sampling`: sampling

These can be extended using the following options:

* `codeInclude` : include additional header files
* `codeOptions` : path to additional header files
* `codeLibs` : linking additional libraries

## Further information

Tutorials

* *none*

Source code

* [codedSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/general/codedSource)
