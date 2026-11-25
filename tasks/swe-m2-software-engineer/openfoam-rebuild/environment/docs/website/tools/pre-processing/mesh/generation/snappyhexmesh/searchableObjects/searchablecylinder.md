<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/searchableObjects/searchablecylinder -->

# searchableCylinder

A cylinder given by two points and a radius.

## Usage

```
cylinder
{
    type            searchableCylinder;
    point1          (1.5 1 -0.5);
    point2          (3.5 2 0.5);
    radius          0.05;
}

```

Where:

| Property | Description | Required |
| --- | --- | --- |
| `point1` | Axis point at the start | yes |
| `point2` | Axis point at the end | yes |
| `radius` | Cylinder radius | yes |
