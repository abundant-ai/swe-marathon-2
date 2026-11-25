<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/quick-reference -->

# Quick reference

The quick reference colours the entries according to:

| Action | Colour |
| --- | --- |
| Required entry |  |
| Change as needed |  |
| Sometimes change |  |
| Usually leave as default |  |
| Deprecated entry |  |

## Top\-level entries

| Keyword | Value type | Default value | Change? |
| --- | --- | --- | --- |
| [castellatedMesh](global.md#keywords-castellatedMesh) | boolean |  |  |
| [snap](global.md#keywords-snap) | boolean |  |  |
| [addLayers](global.md#keywords-addLayers) | boolean |  |  |
| [singleRegionName](global.md#keywords-singleRegionName) | boolean | yes |  |
| [mergePatchFaces](global.md#keywords-mergePatchFaces) | boolean | yes |  |
| [mergeTolerance](global.md#keywords-mergeTolerance) | scalar |  |  |
| [keepPatches](global.md#keywords-keepPatches) | boolean | no |  |
| [debug](global.md#debugging-debug) | label | 0 |  |
| [geometry](quick-reference.md#snappy-quick-reference-geometry) | dictionary |  |  |
| [castellatedMeshControls](quick-reference.md#sec-snappy-quick-reference-castellatedMeshControls) | dictionary |  |  |
| [snapControls](quick-reference.md#sec-snappy-quick-reference-snapControls) | dictionary |  |  |
| [addLayerControls](quick-reference.md#sec-snappy-quick-reference-addLayerControls) | dictionary |  |  |
| [meshQualityControls](quick-reference.md#sec-snappy-quick-reference-meshQualityControls) | dictionary |  |  |
| [debugFlags](quick-reference.md#sec-snappy-quick-reference-debugFlags) | dictionary |  |  |
| [writeFlags](quick-reference.md#sec-snappy-quick-reference-writeFlags) | dictionary |  |  |
| [outputFlags](quick-reference.md#sec-snappy-quick-reference-outputFlags) | dictionary |  |  |

## Geometry

Sub\-dictionary: `geometry`

| Keyword | Value type | Default value | Change? |
| --- | --- | --- | --- |
| \<geometryName\> | dictionary |  |  |
| \<geometryName\>.type | geometryType |  |  |
| \<geometryName\>.name | word |  |  |
| \<geometryName\>.regions | word |  |  |

## Castellated mesh controls

Sub\-dictionary: `castellatedMeshControls`

| Keyword | Value type | Default value | Change? |
| --- | --- | --- | --- |
| [maxLocalCells](castellation.md#castellation-maxLocalCells) | label |  |  |
| [maxGlobalCells](castellation.md#castellation-maxGlobalCells) | label |  |  |
| [minRefinementCells](castellation.md#castellation-minRefinementCells) | label |  |  |
| [maxLoadUnbalance](castellation.md#castellation-maxLoadUnbalance) | scalar |  |  |
| [nCellsBetweenLevels](castellation.md#castellation-nCellsBetweenLevels) | label |  |  |
| [features](castellation.md#castellation-features) | dictionary |  |  |
| features.file | string |  |  |
| features.level | label |  |  |
| features.levels | (scalar label) |  |  |
| [refinementSurfaces](castellation.md#castellation-refinementSurfaces) | dictionary |  |  |
| refinementSurfaces.\<geometryName\> | dictionary |  |  |
| refinementSurfaces.\<geometryName\>.level | label |  |  |
| refinementSurfaces.\<geometryName\>.regions | dictionary |  |  |
| [resolveFeatureAngle](castellation.md#castellation-resolveFeatureAngle) | scalar |  |  |
| [gapLevelIncrement](castellation.md#castellation-gapLevelIncrement) | label |  |  |
| [planarAngle](castellation.md#castellation-planarAngle) | scalar |  |  |
| [refinementRegions](castellation.md#castellation-refinementRegions) | dictionary |  |  |
| [limitRegions](castellation.md#castellation-limitRegions) | dictionary |  |  |
| [locationInMesh](castellation.md#castellation-locationInMesh) | point |  |  |
| [locationsInMesh](castellation.md#castellation-locationsInMesh) | list of (point word) |  |  |
| [allowFreeStandingZoneFaces](castellation.md#castellation-allowFreeStandingZoneFaces) | boolean |  |  |
| [faceZoneControls](castellation.md#castellation-faceZoneControls) | dictionary |  |  |
| [locationsOutsideMesh](castellation.md#castellation-locationsOutsideMes) | list of points |  |  |
| [handleSnapProblems](castellation.md#castellation-handleSnapProblems) | boolean |  |  |
| [useTopologicalSnapDetection](castellation.md#castellation-useTopologicalSnapDetection) | boolean |  |  |
| [interfaceRefine](castellation.md#castellation-interfaceRefine) | boolean |  |  |
| [nCellZoneErodeIter](castellation.md#castellation-nCellZoneErodeIter) | label |  |  |

## Snap controls

Sub\-dictionary: `snapControls`

| Keyword | Value type | Default value | Change? |
| --- | --- | --- | --- |
| [nSmoothPatch](snapping.md#keywords-nSmoothPatch) | label |  |  |
| [nSmoothInternal](snapping.md#keywords-nSmoothInternal) | label |  |  |
| [tolerance](snapping.md#keywords-tolerance) | scalar |  |  |
| [nSolveIter](snapping.md#keywords-nSolveIter) | label |  |  |
| [nRelaxIter](snapping.md#keywords-nRelaxIter) | label |  |  |
| [detectNearSurfaceSnap](snapping.md#keywords-detectNearSurfaceSnap) | boolean |  |  |
| [nFeatureSnapIter](snapping.md#keywords-nFeatureSnapIter) | label |  |  |
| [implicitFeatureSnap](snapping.md#keywords-implicitFeatureSnap) | boolean | false |  |
| [explicitFeatureSnap](snapping.md#keywords-explicitFeatureSnap) | boolean | true |  |
| [multiRegionFeatureSnap](snapping.md#keywords-multiRegionFeatureSnap) | boolean |  |  |
| [nFaceSplitInterval](snapping.md#keywords-nFaceSplitInterval) | label |  |  |
| [detectBaffles](snapping.md#keywords-detectBaffles) | boolean |  |  |
| [releasePoints](snapping.md#keywords-releasePoints) | boolean |  |  |
| [stringFeatures](snapping.md#keywords-stringFeatures) | boolean |  |  |
| [avoidDiagonal](snapping.md#keywords-avoidDiagonal) | boolean |  |  |
| [concaveAngle](snapping.md#keywords-concaveAngle) | scalar |  |  |
| [minAreaRatio](snapping.md#keywords-minAreaRatio) | scalar |  |  |
| [strictRegionSnap](snapping.md#keywords-strictRegionSnap) | boolean |  |  |
| [baffleFeaturePoints](snapping.md#keywords-baffleFeaturePoints) | boolean |  |  |

## Layer controls

Sub\-dictionary: `addLayerControls`

| Keyword | Value type | Default value | Change? |
| --- | --- | --- | --- |
| [relativeSizes](layers.md#keywords-relativeSizes) | boolean |  |  |
| [nBufferCellsNoExtrude](layers.md#keywords-nBufferCellsNoExtrude) | label |  |  |
| [nLayerIter](layers.md#keywords-nLayerIter) | label |  |  |
| [nRelaxedIter](layers.md#keywords-nRelaxedIter) | label |  |  |
| [additionalReporting](layers.md#keywords-additionalReporting) | boolean |  |  |
| [expansionRatio](layers.md#keywords-expansionRatio) | scalar |  |  |
| [finalLayerThickness](layers.md#keywords-finalLayerThickness) | scalar |  |  |
| [firstLayerThickness](layers.md#keywords-firstLayerThickness) | scalar |  |  |
| [thickness](layers.md#keywords-thickness) | scalar |  |  |
| [minThickness](layers.md#keywords-minThickness) | scalar |  |  |
| layers | dictionary |  |  |
| layers.\<patchName\> | dictionary |  |  |
| [layers.\<patchName\>.nSurfaceLayers](layers.md#keywords-nSurfaceLayers) | label |  |  |
| [layers.\<patchName\>.expansionRatio](layers.md#keywords-expansionRatio) | scalar |  |  |
| [layers.\<patchName\>.finalLayerThickness](layers.md#keywords-finalLayerThickness) | scalar |  |  |
| [layers.\<patchName\>.firstLayerThickness](layers.md#keywords-firstLayerThickness) | scalar |  |  |
| [layers.\<patchName\>.thickness](layers.md#keywords-thickness) | scalar |  |  |
| [layers.\<patchName\>.minThickness](layers.md#keywords-minThickness) | scalar |  |  |
| [nGrow](layers.md#keywords-nGrow) | label |  |  |
| [concaveAngle](layers.md#keywords-concaveAngle) | scalar |  |  |
| [featureAngle](layers.md#keywords-featureAngle) | scalar |  |  |
| [mergePatchFacesAngle](layers.md#keywords-mergePatchFacesAngle) | scalar |  |  |
| [maxFaceThicknessRatio](layers.md#keywords-maxFaceThicknessRatio) | scalar |  |  |
| [meshShrinker](layers.md#mesh-shrinking) | word |  |  |
| [solver](layers.md#shrinking-displacementmotionsolver) | word |  |  |
| [nSmoothSurfaceNormals](layers.md#keywords-nSmoothSurfaceNormals) | label |  |  |
| [minMedialAxisAngle](layers.md#keywords-minMedialAxisAngle) | scalar |  |  |
| [minMedianAxisAngle](layers.md#keywords-minMedianAxisAngle) | scalar |  |  |
| [maxThicknessToMedialRatio](layers.md#keywords-maxThicknessToMedialRatio) | scalar |  |  |
| [nSmoothNormals](layers.md#keywords-nSmoothNormals) | label |  |  |
| [nSmoothThickness](layers.md#keywords-nSmoothThickness) | label |  |  |
| [nMedialAxisIter](layers.md#keywords-nMedialAxisIter) | label |  |  |
| [nSmoothDisplacement](layers.md#keywords-nSmoothDisplacement) | label |  |  |
| [layerTerminationAngle](layers.md#keywords-layerTerminationAngle) | scalar |  |  |
| [slipFeatureAngle](layers.md#keywords-slipFeatureAngle) | scalar |  |  |
| [nRelaxIter](layers.md#keywords-nRelaxIter) | label |  |  |

## Mesh quality controls

Sub\-dictionary: `meshQualityControls`

| Keyword | Value type | Default value | Change? |
| --- | --- | --- | --- |
| [maxNonOrtho](meshquality.md#keywords-maxNonOrtho) | scalar |  |  |
| [maxBoundarySkewness](meshquality.md#keywords-maxBoundarySkewness) | scalar |  |  |
| [maxInternalSkewness](meshquality.md#keywords-maxInternalSkewness) | scalar |  |  |
| [maxConcave](meshquality.md#keywords-maxConcave) | scalar |  |  |
| [minVol](meshquality.md#keywords-minVol) | scalar |  |  |
| [minTetQuality](meshquality.md#keywords-minTetQuality) | scalar |  |  |
| [minArea](meshquality.md#keywords-minArea) | scalar |  |  |
| [minTwist](meshquality.md#keywords-minTwist) | scalar |  |  |
| [minDeterminant](meshquality.md#keywords-minDeterminan) | scalar |  |  |
| [minFaceWeight](meshquality.md#keywords-minFaceWeight) | scalar |  |  |
| [minVolRatio](meshquality.md#keywords-minVolRatio) | scalar |  |  |
| [minTriangleTwist](meshquality.md#keywords-minTriangleTwist) | scalar |  |  |
| [minVolCollapseRatio](meshquality.md#keywords-minVolCollapseRatio) | scalar |  |  |
| [minFaceFlatness](meshquality.md#keywords-minFaceFlatness) | scalar |  |  |
| [relaxed](meshquality.md#keywords-relaxed) | dictionary |  |  |
| [nSmoothScale](meshquality.md#keywords-nSmoothScale) | label |  |  |
| [errorReduction](meshquality.md#keywords-errorReduction) | scalar |  |  |

## Debug flags

Sub\-dictionary: `debugFlags`

| Keyword | Value type | Default value | Change? |
| --- | --- | --- | --- |
| mesh |  |  |  |
| intersections |  |  |  |
| featureSeeds |  |  |  |
| attraction |  |  |  |
| layerInfo |  |  |  |

## Write flags

Sub\-dictionary: `writeFlags`

| Keyword | Options | Default value | Change? |
| --- | --- | --- | --- |
| mesh |  |  |  |
| noRefinement |  |  |  |
| scalarLevels |  |  |  |
| layerSets |  |  |  |
| layerFields |  |  |  |

## Output flags

Sub\-dictionary: `outputFlags`

| Keyword | Options | Default value | Change? |
| --- | --- | --- | --- |
| layerInfo |  |  |  |
