<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/searchableObjects/searchablebox -->

# searchableBox

A cuboid given by two points on its diagonal.

## Usage

```
box
{
    type            searchableBox;
    min             (1.5 1 -0.5);
    max             (3.5 2 0.5);
}

```

Where:

| Property | Description | Required |
| --- | --- | --- |
| `min` | Box minimum point | yes |
| `max` | Box maximum point | yes |
