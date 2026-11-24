<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmNutSource -->

# atmNutSource

## Properties

* The `atmNutSource` adds/subtracts a given artificial turbulent
viscosity field to/from `nut` for atmospheric boundary layer modelling.
* The `atmNutSource` can be applied on any RAS turbulence model.
* The `atmNutSource` inherits the traits of the
[fvOption](../../../../../../fundamentals/case-structure/fvoptions.md), and `cellSetOption`.

Corrections applied to:

`nut`
: Turbulent viscosity \[m2^22/s]

Required fields:

`nut`
: Turbulent viscosity \[m2^22/s]

`artNut`
: Artificial turbulent viscosity \[m2^22/s]

## Model equations

The model expression:

νt\+\=νtart \\nu\_t \+\= \\nu\_{t\_{art}}νt​\+\=νtart​​
Where:

νt\\nu\_tνt​
: Turbulent viscosity \[m2/s]

νtart\\nu\_{t\_{art}}νtart​​
: Artificial turbulent viscosity \[m2/s]

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmNutSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmNutSource;

    atmNutSourceCoeffs
    {
        // Mandatory (inherited) entries (unmodifiable)
        selectionMode    all;

        // Optional entries (unmodifiable)
        nut              artNut;
    }

    // Optional (inherited) entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: atmNutSource | word | yes | \- |
| nut | Field name of artificial `nut` | word | no | artNut |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Source code

* [atmNutSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmNutSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
