#include "BRWorld.h"

#include "BRLoot.h"
#include "BRVehicle.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialParameters.h"
#include "Math/RandomStream.h"

#include <initializer_list>

namespace
{
    FLinearColor Color(uint8 Red, uint8 Green, uint8 Blue)
    {
        return FLinearColor::FromSRGBColor(FColor(Red, Green, Blue));
    }

    const FLinearColor Grass = Color(100, 111, 70);
    const FLinearColor DryGrass = Color(116, 118, 79);
    const FLinearColor Gravel = Color(122, 114, 95);
    const FLinearColor Asphalt = Color(72, 74, 70);
    const FLinearColor Paint = Color(174, 164, 121);
    const FLinearColor Concrete = Color(145, 140, 126);
    const FLinearColor Plaster = Color(155, 150, 130);
    const FLinearColor BlueSteel = Color(80, 106, 112);
    const FLinearColor RustSteel = Color(128, 83, 60);
    const FLinearColor Roof = Color(81, 83, 78);
    const FLinearColor Trim = Color(100, 97, 80);
    const FLinearColor Wood = Color(120, 91, 66);
    const FLinearColor Bark = Color(85, 72, 56);
    const FLinearColor Leaf = Color(59, 83, 54);
    const FLinearColor LeafLight = Color(80, 100, 62);

    FActorSpawnParameters SpawnParameters()
    {
        FActorSpawnParameters Params;
        Params.ObjectFlags |= RF_Transient;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        return Params;
    }

    class FScenery
    {
    public:
        explicit FScenery(UWorld& InWorld)
            : World(InWorld),
              Cube(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"))),
              Cylinder(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"))),
              Sphere(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")))
        {
        }

        void Box(const FVector& Center, const FVector& Size, const FLinearColor& Tint,
            const FRotator& Rotation = FRotator::ZeroRotator, bool bSolid = true) const
        {
            Place(Cube, Center, Size, Rotation, Tint, bSolid);
        }

        void Column(const FVector& Center, double Diameter, double Height,
            const FLinearColor& Tint, bool bSolid = true) const
        {
            Place(Cylinder, Center, FVector(Diameter, Diameter, Height),
                FRotator::ZeroRotator, Tint, bSolid);
        }

        void Canopy(const FVector& Center, const FVector& Size, const FLinearColor& Tint) const
        {
            Place(Sphere, Center, Size, FRotator::ZeroRotator, Tint, false);
        }

    private:
        void Place(UStaticMesh* Mesh, const FVector& Center, const FVector& Size,
            const FRotator& Rotation, const FLinearColor& Tint, bool bSolid) const
        {
            if (!Mesh)
            {
                return;
            }
            const FTransform Transform(Rotation, Center, Size / 100.0);
            AStaticMeshActor* Actor = World.SpawnActor<AStaticMeshActor>(
                AStaticMeshActor::StaticClass(), Transform, SpawnParameters());
            if (!Actor)
            {
                return;
            }
            UStaticMeshComponent* Component = Actor->GetStaticMeshComponent();
            Component->SetMobility(EComponentMobility::Movable);
            Component->SetStaticMesh(Mesh);
            Component->SetCollisionProfileName(bSolid ? TEXT("BlockAll") : TEXT("NoCollision"));
            Component->SetGenerateOverlapEvents(false);
            Component->SetMobility(EComponentMobility::Static);
            if (World.GetNetMode() != NM_DedicatedServer)
            {
                BRWorld::TintMesh(*Component, Tint);
            }
        }

        UWorld& World;
        UStaticMesh* Cube;
        UStaticMesh* Cylinder;
        UStaticMesh* Sphere;
    };

    void Road(const FScenery& Scene, std::initializer_list<FVector> Waypoints)
    {
        const FVector* Previous = nullptr;
        for (const FVector& Point : Waypoints)
        {
            Scene.Column(Point + FVector(0.0, 0.0, 2.0), 510.0, 2.0, Gravel, false);
            Scene.Column(Point + FVector(0.0, 0.0, 4.0), 390.0, 2.0, Asphalt, false);
            if (Previous)
            {
                const FVector Delta = Point - *Previous;
                const double Length = Delta.Size2D();
                const FRotator Heading(0.0, Delta.Rotation().Yaw, 0.0);
                const FVector Center = (*Previous + Point) * 0.5;
                Scene.Box(Center + FVector(0.0, 0.0, 2.0), FVector(Length, 510.0, 2.0),
                    Gravel, Heading, false);
                Scene.Box(Center + FVector(0.0, 0.0, 4.0), FVector(Length, 390.0, 2.0),
                    Asphalt, Heading, false);
                for (double Distance = 265.0; Distance < Length - 265.0; Distance += 515.0)
                {
                    const FVector Stripe = *Previous + Delta * (Distance / Length);
                    Scene.Box(Stripe + FVector(0.0, 0.0, 6.0), FVector(133.0, 9.0, 2.0),
                        Paint, Heading, false);
                }
            }
            Previous = &Point;
        }
    }

    void Building(const FScenery& Scene, const FVector& Pivot, double Yaw,
        const FLinearColor& Walls)
    {
        const FRotator Rotation(0.0, Yaw, 0.0);
        auto Box = [&](const FVector& Local, const FVector& Size, const FLinearColor& Tint,
            const FRotator& Angle = FRotator::ZeroRotator, bool bSolid = true)
        {
            Scene.Box(Pivot + Rotation.RotateVector(Local), Size, Tint,
                FRotator(Angle.Pitch, Yaw + Angle.Yaw, Angle.Roll), bSolid);
        };

        Box(FVector(0, 0, 4), FVector(650, 700, 8), Concrete);
        Box(FVector(-312, 0, 145), FVector(26, 680, 290), Walls);
        Box(FVector(312, -217, 145), FVector(26, 246, 290), Walls);
        Box(FVector(312, 217, 145), FVector(26, 246, 290), Walls);
        Box(FVector(312, 0, 261), FVector(26, 188, 58), Walls);

        for (const double Side : {-1.0, 1.0})
        {
            const double SideWall = Side * 332.0;
            Box(FVector(-201, SideWall, 145), FVector(228, 26, 290), Walls);
            Box(FVector(201, SideWall, 145), FVector(228, 26, 290), Walls);
            Box(FVector(0, SideWall, 56), FVector(174, 26, 112), Walls);
            Box(FVector(0, SideWall, 254), FVector(174, 26, 72), Walls);
            Box(FVector(0, SideWall, 108), FVector(185, 38, 9), Concrete);

            Box(FVector(312, Side * 107.0, 120), FVector(38, 9, 224), Trim);
            Box(FVector(0, Side * 342.0, 19), FVector(620, 13, 28), Concrete);
            Box(FVector(0, Side * 178.0, 319.0), FVector(682, 367, 18), Roof,
                FRotator(0.0, 0.0, Side * -8.0));
            Box(FVector(0, Side * 355.0, 292.0), FVector(682, 18, 24), Trim);
        }

        Box(FVector(0, 0, 347), FVector(686, 36, 14), Roof);
        Box(FVector(358, 0, 251), FVector(90, 230, 12), BlueSteel);
        Box(FVector(402, -114, 124), FVector(14, 14, 251), Trim);
        Box(FVector(402, 114, 124), FVector(14, 14, 251), Trim);
        Box(FVector(-201, 237, 47), FVector(111, 111, 77), Wood);
        Box(FVector(-202, 237, 88), FVector(116, 116, 9), Trim);
    }

    void Ramp(const FScenery& Scene, const FVector& Base, double Yaw)
    {
        constexpr double Rise = 45.0;
        constexpr double Run = 350.0;
        const FRotator Heading(0.0, Yaw, 0.0);
        const FVector Forward = Heading.Vector();
        const double Pitch = FMath::RadiansToDegrees(FMath::Atan2(Rise, Run));
        Scene.Box(Base + Forward * (Run * 0.5) + FVector(0.0, 0.0, Rise * 0.5 - 10.0),
            FVector(FMath::Sqrt(Run * Run + Rise * Rise), 425.0, 20.0), Concrete,
            FRotator(Pitch, Yaw, 0.0));
        Scene.Box(Base + Forward * (Run + 265.0) + FVector(0.0, 0.0, 22.5),
            FVector(530.0, 425.0, 45.0), Gravel, Heading);
        Scene.Box(Base + Forward * (Run * 1.5 + 530.0) + FVector(0.0, 0.0, Rise * 0.5 - 10.0),
            FVector(FMath::Sqrt(Run * Run + Rise * Rise), 425.0, 20.0), Concrete,
            FRotator(-Pitch, Yaw, 0.0));
    }

    void LowBarrier(const FScenery& Scene, const FVector& Center, double Yaw)
    {
        const FRotator Rotation(0.0, Yaw, 0.0);
        Scene.Box(Center + FVector(0, 0, 21), FVector(298, 67, 42), Concrete, Rotation);
        Scene.Box(Center + FVector(0, 0, 65), FVector(284, 44, 52), Concrete, Rotation);
        Scene.Box(Center + FVector(0, 0, 90), FVector(286, 47, 9), Trim, Rotation);
    }

    void PalletCrate(const FScenery& Scene, const FVector& Center, double Yaw)
    {
        const FRotator Rotation(0.0, Yaw, 0.0);
        Scene.Box(Center + FVector(0, 0, 12), FVector(133, 101, 24), Trim, Rotation);
        Scene.Box(Center + FVector(0, 0, 57), FVector(120, 94, 78), Wood, Rotation);
        for (double Offset : {-42.0, 42.0})
        {
            Scene.Box(Center + Rotation.RotateVector(FVector(Offset, 0, 99)),
                FVector(15, 97, 9), Trim, Rotation);
        }
    }

    void Grove(const FScenery& Scene, const FVector& Center, int32 Count, FRandomStream& Random)
    {
        for (int32 Index = 0; Index < Count; ++Index)
        {
            const float X = Random.FRandRange(-640.0f, 640.0f);
            const float Y = Random.FRandRange(-570.0f, 570.0f);
            const FVector Base = Center + FVector(X, Y, 0.0);
            const double TrunkHeight = Random.FRandRange(245.0f, 385.0f);
            const double Width = Random.FRandRange(168.0f, 240.0f);
            Scene.Column(Base + FVector(0.0, 0.0, TrunkHeight * 0.5), 37.0,
                TrunkHeight, Bark);
            Scene.Canopy(Base + FVector(0.0, 0.0, TrunkHeight - 19.0),
                FVector(Width, Width, 159.0), Leaf);
            Scene.Canopy(Base + FVector(45.0, 17.0, TrunkHeight + 42.0),
                FVector(Width * 0.85, Width, 154.0), LeafLight);
        }
    }

    void Lights(UWorld& World)
    {
        if (World.GetNetMode() == NM_DedicatedServer)
        {
            return;
        }
        const FActorSpawnParameters Params = SpawnParameters();
        World.SpawnActor<ASkyAtmosphere>(Params);
        if (ADirectionalLight* Sun = World.SpawnActor<ADirectionalLight>(
            FVector::ZeroVector, FRotator(-43.0, -27.0, 0.0), Params))
        {
            if (UDirectionalLightComponent* Light = Sun->FindComponentByClass<UDirectionalLightComponent>())
            {
                Light->SetMobility(EComponentMobility::Movable);
                Light->SetIntensity(6.0f);
                Light->SetLightColor(FLinearColor(1.0, 0.91, 0.77));
                Light->SetAtmosphereSunLight(true);
            }
        }
        if (ASkyLight* Sky = World.SpawnActor<ASkyLight>(Params))
        {
            USkyLightComponent* Light = Sky->GetLightComponent();
            Light->SetMobility(EComponentMobility::Movable);
            Light->SetIntensity(0.85f);
            Light->SetRealTimeCaptureEnabled(true);
        }
        if (AExponentialHeightFog* Haze = World.SpawnActor<AExponentialHeightFog>(Params))
        {
            Haze->GetComponent()->SetFogDensity(0.013f);
            Haze->GetComponent()->SetFogHeightFalloff(0.43f);
        }
    }
}

void BRWorld::TintMesh(UStaticMeshComponent& Component, const FLinearColor& Color)
{
    UMaterialInterface* Base = Component.GetMaterial(0);
    if (!Base)
    {
        return;
    }
    TArray<FMaterialParameterInfo> Parameters;
    TArray<FGuid> Ids;
    Base->GetAllVectorParameterInfo(Parameters, Ids);
    if (Parameters.IsEmpty())
    {
        return;
    }

    FName Name = Parameters[0].Name;
    for (const FMaterialParameterInfo& Parameter : Parameters)
    {
        if (Parameter.Name == TEXT("Color") || Parameter.Name == TEXT("BaseColor")
            || Parameter.Name == TEXT("Base Color"))
        {
            Name = Parameter.Name;
            break;
        }
    }
    if (UMaterialInstanceDynamic* Material = Component.CreateDynamicMaterialInstance(0, Base))
    {
        Material->SetVectorParameterValue(Name, Color);
    }
}

void BRWorld::BuildScenery(UWorld& World)
{
    const FScenery Scene(World);
    Scene.Box(FVector(0, 0, -95), FVector(20000, 20000, 190), Grass);
    Scene.Box(FVector(-9950, 0, 64), FVector(140, 19800, 128), DryGrass);
    Scene.Box(FVector(9950, 0, 64), FVector(140, 19800, 128), DryGrass);
    Scene.Box(FVector(0, -9950, 64), FVector(19800, 140, 128), DryGrass);
    Scene.Box(FVector(0, 9950, 64), FVector(19800, 140, 128), DryGrass);

    Scene.Box(FVector(-4870, -3330, 1), FVector(1800, 1250, 2), DryGrass,
        FRotator(0, 3, 0), false);
    Scene.Box(FVector(4920, 2800, 1), FVector(1700, 1350, 2), DryGrass,
        FRotator(0, -15, 0), false);
    Scene.Box(FVector(-420, 1250, 1), FVector(1710, 1280, 2), DryGrass,
        FRotator(0, -10, 0), false);

    Road(Scene, {
        FVector(-8050, -2600, 0), FVector(-4300, -2800, 0), FVector(-1800, -800, 0),
        FVector(0, 0, 0), FVector(1900, 100, 0), FVector(4700, 2200, 0),
        FVector(7800, 1400, 0),
    });
    Road(Scene, {FVector(0, 0, 0), FVector(-400, 2600, 0), FVector(1000, 4750, 0),
        FVector(2100, 6800, 0)});
    Road(Scene, {FVector(-1800, -800, 0), FVector(-1900, -3500, 0), FVector(150, -5450, 0),
        FVector(2600, -6100, 0)});
    Road(Scene, {FVector(4700, 2200, 0), FVector(4740, -2700, 0), FVector(6240, -5450, 0)});
    Road(Scene, {FVector(-4300, -2800, 0), FVector(-4440, 600, 0), FVector(-3900, 3400, 0)});

    Building(Scene, FVector(-3560, -3660, 0), 24.0, Plaster);
    Building(Scene, FVector(5150, 3410, 0), -110.0, BlueSteel);
    Building(Scene, FVector(-980, 1240, 0), 5.0, RustSteel);
    Building(Scene, FVector(1750, -4320, 0), 140.0, Plaster);
    Building(Scene, FVector(3770, -2370, 0), 30.0, BlueSteel);
    Building(Scene, FVector(-5270, 1660, 0), -14.0, Plaster);

    Ramp(Scene, FVector(-1980, 2070, 0), 106.0);
    Ramp(Scene, FVector(2800, 3290, 0), -12.0);
    for (const FVector& Point : {FVector(-1150, -510, 0), FVector(-940, 330, 0),
             FVector(1120, 510, 0), FVector(1890, -505, 0), FVector(3230, 529, 0),
             FVector(2670, -1710, 0), FVector(-3260, 240, 0), FVector(4230, 3770, 0),
             FVector(-2270, 1860, 0), FVector(-2560, 1990, 0)})
    {
        LowBarrier(Scene, Point, 15.0);
    }
    for (const FVector& Point : {FVector(-4660, -2350, 0), FVector(-3300, -3270, 0),
             FVector(5260, 2940, 0), FVector(4600, 3240, 0), FVector(2060, 910, 0),
             FVector(1620, -3800, 0), FVector(-1360, 810, 0), FVector(3280, -1510, 0)})
    {
        PalletCrate(Scene, Point, 21.0);
    }

    FRandomStream Random(913406);
    for (const FVector& Point : {FVector(-6820, -5550, 0), FVector(-5710, 4120, 0),
             FVector(-2500, 4700, 0), FVector(-2490, -4860, 0), FVector(740, 6280, 0),
             FVector(3400, 4400, 0), FVector(6450, 3900, 0), FVector(7120, -2400, 0),
             FVector(2890, -4500, 0), FVector(785, -3040, 0), FVector(1660, 2420, 0)})
    {
        Grove(Scene, Point, 6, Random);
    }
    Lights(World);
}

void BRWorld::SpawnInteractives(UWorld& World)
{
    if (World.GetNetMode() == NM_Client)
    {
        return;
    }
    struct FLootPlacement
    {
        FVector Position;
        EBRItem Item;
        int32 Count;
    };
    const FLootPlacement Loot[] = {
        {FVector(-4965, -2430, 25), EBRItem::AK47, 1},
        {FVector(-4800, -2400, 25), EBRItem::AKAmmo, 60},
        {FVector(-4470, -3210, 25), EBRItem::M16, 1},
        {FVector(-4310, -3160, 25), EBRItem::M16Ammo, 45},
        {FVector(4990, 2650, 25), EBRItem::M16, 1},
        {FVector(5250, 2710, 25), EBRItem::M16Ammo, 60},
        {FVector(5430, 2650, 25), EBRItem::AK47, 1},
        {FVector(5630, 2640, 25), EBRItem::AKAmmo, 45},
        {FVector(-3400, -3680, 32), EBRItem::AKAmmo, 36},
        {FVector(5200, 3450, 32), EBRItem::M16Ammo, 36},
        {FVector(-935, 1200, 32), EBRItem::AK47, 1},
        {FVector(-1060, 1440, 32), EBRItem::AKAmmo, 38},
        {FVector(1570, -4210, 32), EBRItem::M16, 1},
        {FVector(1800, -4380, 32), EBRItem::M16Ammo, 38},
        {FVector(3770, -2410, 32), EBRItem::AKAmmo, 45},
        {FVector(-5280, 1580, 32), EBRItem::M16Ammo, 45},
        {FVector(1020, -390, 25), EBRItem::M16Ammo, 30},
        {FVector(-330, 455, 25), EBRItem::AKAmmo, 30},
    };

    const FActorSpawnParameters Params = SpawnParameters();
    for (const FLootPlacement& Location : Loot)
    {
        if (ABRLoot* Item = World.SpawnActor<ABRLoot>(
            Location.Position, FRotator::ZeroRotator, Params))
        {
            Item->Configure(Location.Item, Location.Count);
        }
    }
    World.SpawnActor<ABRVehicle>(FVector(-4550, -2790, ABRVehicle::RideHeight),
        FRotator(0.0, -3.0, 0.0), Params);
    World.SpawnActor<ABRVehicle>(FVector(4900, 2130, ABRVehicle::RideHeight),
        FRotator(0.0, -12.0, 0.0), Params);
}

FTransform BRWorld::PlayerSpawn(int32 Slot)
{
    if (Slot == 0)
    {
        return FTransform(FRotator(0.0, 28.0, 0.0), FVector(-5100, -2600, 105), FVector::OneVector);
    }
    return FTransform(FRotator(0.0, -152.0, 0.0), FVector(5100, 2600, 105), FVector::OneVector);
}
