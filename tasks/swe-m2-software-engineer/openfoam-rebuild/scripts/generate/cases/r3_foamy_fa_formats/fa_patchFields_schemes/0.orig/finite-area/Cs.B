/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2606                                 |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       areaScalarField;
    object      Cs;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions          [1 -2 0 0 0 0 0];

internalField       uniform 0.2;

boundaryField
{
    #includeEtc "caseDicts/setConstraintTypes"

    inlet1
    {
        type                 uniformMixed;
        uniformValue         constant 1;
        uniformGradient      constant 0;
        uniformValueFraction table ((0 1) (0.6 0.2));
        value                uniform 0.2;
    }

    inlet2
    {
        type            uniformFixedGradient;
        uniformGradient linearRamp;
        uniformGradientCoeffs { start 0; duration 0.6; }
        value           uniform 0.2;
    }

    outlet
    {
        type            uniformFixedValue;
        uniformValue    sine;
        uniformValueCoeffs { frequency 1; amplitude 0.1; scale 1; level 0.2; }
        value           uniform 0.2;
    }

    bound
    {
        type            fixedValue;
        value           uniform 0;
    }
}


// ************************************************************************* //
