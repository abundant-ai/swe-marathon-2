<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/specie -->

# Specie

## Options

The specie model represents the lowest\-level thermophysical entity, responsible
for:

* the specie name,
* molecular weight, WWW \[kg/kmol],
* number of mols, nnn \[mol], and
* gas constant RgR\_gRg​ \[J/kg/K].

## Usage

```
specie
{
    molWeight       <molecular-weight>

    // Optional; default = 1
    massFraction    <fraction>
}

```

Note that the gas constant is a derived quantity, calculated as:

Rg\=RWR\_g \= \\frac{R}{W}Rg​\=WR​
Where RRR is the universal gas constant with the value 8\.314 \[J/K/mol]

## Further information

Source code

* [specie](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/specie)
