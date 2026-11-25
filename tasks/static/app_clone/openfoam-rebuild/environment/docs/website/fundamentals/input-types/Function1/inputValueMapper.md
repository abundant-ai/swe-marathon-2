<!-- https://doc.openfoam.com/2606/fundamentals/input-types/Function1/inputValueMapper -->

# inputValueMapper

## Description

The `inputValueMapper` `Function1` is a wrapper that maps the input value prior to it being used by another `Function1`

## Usage

Example of the `inputValueMapper` `Function1` to set the value of the entry
`myValue1`

```
myValue
{
    type            inputValueMapper;
    mode            <mode-type>;
    value           <Function1>;
}

```

where the entries are described below:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: inputValueMapper | word | yes | \- |
| mode | Mode type \- see below | word | yes | \- |
| value | Function1 type to supply the value | dictionary | yes | \- |

The `<mode-type>` can be set to:

* `minMax` : limit the value to within user\-specified minimum and maximum
values
* `function` : use the result of an additional `Function1` as the input to
the value `Function1`

Example showing `minMax` usage to limit the return value of a polynomial:

```
myValue
{
    type            inputValueMapper;
    mode            minMax;

    min             0.4;
    max             1.4;

    value polynomial
    (
        (5 1)
        (-2 2)
        (-2 3)
        (1 4)
    );
}

```

Here the return value will be:

* poly(0\.4\) for x \<\= 0\.4;
* poly(1\.4\) for x \>\= 1\.4; and
* poly(x) for 0\.4 \< x \< 1\.4\.

Example showing `function` usage to supply a patch mass flux returned from a
`functionObjectValue` `Function1` to a table lookup:

```
myValue
{
    type            inputValueMapper;
    mode            function;

    function
    {
        type            functionObjectValue;
        functionObject  surfaceFieldValue1;
        functionObjectResult sum(outlet,phi);
    }

    value
    {
        type        table;
        file        "<system>/fanCurve.txt";
    }
}

```

## Further information

Source code

* [InputValueMapper](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/primitives/functions/Function1/InputValueMapper)

Tutorial

* [simpleCar](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/simpleCar)
* [propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)

API:

* [Foam::Function1Types::InputValueMapper](https://api.openfoam.com/2606/Foam_Function1Types_InputValueMapper.html)

**History:** Introduced in version [v2112](https://www.openfoam.com/news/main-news/openfoam-v2112)
