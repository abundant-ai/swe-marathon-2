#include "BRVehicle.h"

#include "BRCharacter.h"
#include "BRMatch.h"
#include "BRWorld.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
    const FVector HullExtent(160.0, 90.0, 70.0);
    constexpr float InteractionDistance = 350.0f;
    constexpr float TopSpeed = 1560.0f;
    constexpr float ReverseSpeed = 490.0f;

    TOptional<double> GroundHeight(const UWorld& World, const FVector& Point,
        const FCollisionQueryParams& Query)
    {
        FHitResult Hit;
        if (World.LineTraceSingleByChannel(Hit, Point + FVector(0.0, 0.0, 16.0),
            Point - FVector(0.0, 0.0, 350.0), ECC_Visibility, Query)
            && !Hit.bStartPenetrating && Hit.ImpactNormal.Z >= 0.72)
        {
            return Hit.ImpactPoint.Z;
        }
        return {};
    }
}

ABRVehicle::ABRVehicle()
{
    PrimaryActorTick.bCanEverTick = true;
    SetReplicates(true);
    SetReplicateMovement(true);
    SetNetUpdateFrequency(24.0f);

    Collision = CreateDefaultSubobject<UBoxComponent>(TEXT("VehicleHull"));
    Collision->InitBoxExtent(HullExtent);
    Collision->SetCollisionProfileName(TEXT("BlockAllDynamic"));
    Collision->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    Collision->SetGenerateOverlapEvents(false);
    SetRootComponent(Collision);

    static const ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(
        TEXT("/Engine/BasicShapes/Cube.Cube"));
    static const ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(
        TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));

    const FLinearColor Steel = FLinearColor::FromSRGBColor(FColor(49, 55, 55));
    const FLinearColor Body = FLinearColor::FromSRGBColor(FColor(56, 112, 110));
    const FLinearColor Roof = FLinearColor::FromSRGBColor(FColor(198, 196, 169));
    const FLinearColor Window = FLinearColor::FromSRGBColor(FColor(35, 49, 57));
    const FLinearColor Tire = FLinearColor::FromSRGBColor(FColor(34, 33, 31));
    const FLinearColor Rim = FLinearColor::FromSRGBColor(FColor(128, 129, 124));
    const FLinearColor WhiteLamp = FLinearColor::FromSRGBColor(FColor(229, 215, 166));
    const FLinearColor RedLamp = FLinearColor::FromSRGBColor(FColor(149, 44, 33));

    auto Box = [this](const TCHAR* Name, const FVector& Center, const FVector& Size,
        const FLinearColor& Color, const FRotator& Rotation = FRotator::ZeroRotator)
    {
        Paint.Emplace(AddPart(FName(Name), Cube.Object, Center, Size, Rotation), Color);
    };

    Box(TEXT("Frame"), FVector(0, 0, -23), FVector(310, 147, 20), Steel);
    Box(TEXT("Body"), FVector(0, 0, 0), FVector(299, 148, 48), Body);
    Box(TEXT("Hood"), FVector(101, 0, 18), FVector(99, 140, 18), Body);
    Box(TEXT("Cabin"), FVector(5, 0, 37), FVector(113, 131, 56), Body);
    Box(TEXT("Roof"), FVector(2, 0, 64), FVector(116, 137, 8), Roof);
    Box(TEXT("Windscreen"), FVector(61, 0, 43), FVector(3, 115, 37), Window);
    Box(TEXT("RearWindow"), FVector(-53, 0, 43), FVector(3, 112, 34), Window);
    Box(TEXT("SideGlassLeft"), FVector(9, -66, 45), FVector(85, 3, 28), Window);
    Box(TEXT("SideGlassRight"), FVector(9, 66, 45), FVector(85, 3, 28), Window);
    Box(TEXT("BedFloor"), FVector(-103, 0, 20), FVector(83, 106, 7), Steel);
    Box(TEXT("BedRailLeft"), FVector(-102, -66, 28), FVector(87, 14, 17), Body);
    Box(TEXT("BedRailRight"), FVector(-102, 66, 28), FVector(87, 14, 17), Body);
    Box(TEXT("Tailgate"), FVector(-145, 0, 26), FVector(9, 134, 22), Body);
    Box(TEXT("FrontGrille"), FVector(151, 0, 5), FVector(7, 95, 23), Steel);
    Box(TEXT("FrontBumper"), FVector(155, 0, -19), FVector(10, 149, 11), Steel);
    Box(TEXT("RearBumper"), FVector(-155, 0, -19), FVector(10, 150, 11), Steel);

    for (int32 Side = 0; Side < 2; ++Side)
    {
        const double Sign = Side == 0 ? -1.0 : 1.0;
        Box(*FString::Printf(TEXT("Headlamp%d"), Side), FVector(153, Sign * 59, 8),
            FVector(5, 19, 14), WhiteLamp);
        Box(*FString::Printf(TEXT("TailLamp%d"), Side), FVector(-151, Sign * 62, 11),
            FVector(5, 15, 11), RedLamp);
        for (int32 Axle = 0; Axle < 2; ++Axle)
        {
            const double WheelX = Axle == 0 ? -102.0 : 102.0;
            const FRotator WheelRotation(0.0, 0.0, 90.0);
            Paint.Emplace(AddPart(FName(*FString::Printf(TEXT("Wheel%d%d"), Axle, Side)),
                Cylinder.Object, FVector(WheelX, Sign * 74.0, -41.0),
                FVector(68.0, 68.0, 31.0), WheelRotation), Tire);
            Paint.Emplace(AddPart(FName(*FString::Printf(TEXT("Hub%d%d"), Axle, Side)),
                Cylinder.Object, FVector(WheelX, Sign * 89.0, -41.0),
                FVector(37.0, 37.0, 3.0), WheelRotation), Rim);
        }
    }
}

UStaticMeshComponent* ABRVehicle::AddPart(const FName& Name, UStaticMesh* Mesh,
    const FVector& Center, const FVector& Size, const FRotator& Rotation)
{
    UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Name);
    Part->SetupAttachment(Collision);
    Part->SetStaticMesh(Mesh);
    Part->SetRelativeLocation(Center);
    Part->SetRelativeRotation(Rotation);
    Part->SetRelativeScale3D(Size / 100.0);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    return Part;
}

void ABRVehicle::BeginPlay()
{
    Super::BeginPlay();
    SetActorTickEnabled(HasAuthority());
    for (const TPair<UStaticMeshComponent*, FLinearColor>& Part : Paint)
    {
        BRWorld::TintMesh(*Part.Key, Part.Value);
    }
}

void ABRVehicle::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (HasAuthority() && EndPlayReason == EEndPlayReason::Destroyed && IsValid(Driver))
    {
        TryExit(Driver, true);
    }
    Super::EndPlay(EndPlayReason);
}

void ABRVehicle::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABRVehicle, Driver);
    DOREPLIFETIME(ABRVehicle, ForwardSpeed);
}

bool ABRVehicle::TryEnter(ABRCharacter* Character)
{
    const ABRGameState* Match = GetWorld()->GetGameState<ABRGameState>();
    if (!HasAuthority() || !Match || !Match->IsPlaying() || !IsValid(Character)
        || Character->IsEliminated() || Character->GetVehicle() || IsValid(Driver)
        || FVector::DistSquared(Character->GetActorLocation(), GetActorLocation())
            > FMath::Square(InteractionDistance))
    {
        return false;
    }

    FCollisionQueryParams Query(SCENE_QUERY_STAT(EnterVehicle), false, this);
    Query.AddIgnoredActor(Character);
    if (GetWorld()->LineTraceTestByChannel(Character->GetPawnViewLocation(),
        GetActorLocation() + FVector(0.0, 0.0, 12.0), ECC_Visibility, Query))
    {
        return false;
    }

    ResetControls();
    Driver = Character;
    Character->SetVehicle(this);
    ForceNetUpdate();
    return true;
}

TOptional<FVector> ABRVehicle::FindExit(const ABRCharacter& Character) const
{
    const FVector Origin = GetActorLocation();
    const FRotator Yaw(0.0, GetActorRotation().Yaw, 0.0);
    const UCapsuleComponent* Capsule = Character.GetCapsuleComponent();
    const FCollisionShape Shape = FCollisionShape::MakeCapsule(
        Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight());
    const double SideDistance = HullExtent.Y + Capsule->GetScaledCapsuleRadius() + 40.0;
    const double EndDistance = HullExtent.X + Capsule->GetScaledCapsuleRadius() + 45.0;
    const FVector Offsets[] = {
        FVector(-30.0, -SideDistance, 0.0), FVector(-30.0, SideDistance, 0.0),
        FVector(-EndDistance, 0.0, 0.0), FVector(EndDistance, 0.0, 0.0),
    };

    FCollisionQueryParams GroundQuery(SCENE_QUERY_STAT(ExitVehicleGround), false, this);
    GroundQuery.AddIgnoredActor(&Character);
    const FCollisionQueryParams ClearanceQuery(SCENE_QUERY_STAT(ExitVehicleClearance), false, &Character);
    for (const FVector& Offset : Offsets)
    {
        FVector Candidate = Origin + Yaw.RotateVector(Offset);
        const TOptional<double> Floor = GroundHeight(*GetWorld(), Candidate, GroundQuery);
        if (!Floor.IsSet() || FMath::Abs(Floor.GetValue() - (Origin.Z - RideHeight)) > 95.0)
        {
            continue;
        }
        Candidate.Z = Floor.GetValue() + Capsule->GetScaledCapsuleHalfHeight() + 3.0;
        if (!GetWorld()->OverlapBlockingTestByProfile(Candidate, FQuat::Identity,
            TEXT("Pawn"), Shape, ClearanceQuery))
        {
            return Candidate;
        }
    }
    return {};
}

bool ABRVehicle::TryExit(ABRCharacter* Character, bool bForce)
{
    if (!HasAuthority() || !IsValid(Character) || Driver != Character)
    {
        return false;
    }
    const TOptional<FVector> SafeExit = FindExit(*Character);
    if (!bForce && (FMath::Abs(ForwardSpeed) > 240.0f || !SafeExit.IsSet()))
    {
        return false;
    }

    Driver = nullptr;
    ResetControls();
    Character->SetVehicle(nullptr);
    const FRotator Yaw(0.0, GetActorRotation().Yaw, 0.0);
    const FVector Target = SafeExit.IsSet() ? SafeExit.GetValue()
        : GetActorLocation() + Yaw.RotateVector(FVector(-75.0, -155.0, 110.0));
    Character->SetActorLocationAndRotation(Target, Yaw, false, nullptr, ETeleportType::TeleportPhysics);
    Character->ForceNetUpdate();
    ForceNetUpdate();
    return true;
}

void ABRVehicle::SetDriveInput(ABRCharacter* Character, float Throttle, float Steering, bool bBrake)
{
    if (!HasAuthority() || !IsValid(Character) || Driver != Character
        || Character->IsEliminated() || !FMath::IsFinite(Throttle) || !FMath::IsFinite(Steering))
    {
        return;
    }
    DriveThrottle = FMath::Clamp(Throttle, -1.0f, 1.0f);
    DriveSteering = FMath::Clamp(Steering, -1.0f, 1.0f);
    bDriveBrake = bBrake;
    LastDriveInputTime = GetWorld()->GetTimeSeconds();
}

void ABRVehicle::ResetControls()
{
    DriveThrottle = 0.0f;
    DriveSteering = 0.0f;
    bDriveBrake = false;
    ForwardSpeed = 0.0f;
}

void ABRVehicle::Drive(float Seconds)
{
    const float TargetSpeed = bDriveBrake ? 0.0f
        : (DriveThrottle >= 0.0f ? TopSpeed : ReverseSpeed) * DriveThrottle;
    const float Acceleration = bDriveBrake ? 1900.0f : (DriveThrottle == 0.0f ? 430.0f : 720.0f);
    ForwardSpeed = FMath::FInterpConstantTo(ForwardSpeed, TargetSpeed, Seconds, Acceleration);
    if (FMath::Abs(ForwardSpeed) < 1.0f)
    {
        return;
    }

    const FVector Location = GetActorLocation();
    FRotator Rotation(0.0, GetActorRotation().Yaw, 0.0);
    const float TurnScale = FMath::Clamp(ForwardSpeed / 500.0f, -1.0f, 1.0f);
    const FRotator Turn(0.0, Rotation.Yaw + DriveSteering * TurnScale * 62.0 * Seconds, 0.0);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(VehicleDrive), false, this);
    Query.AddIgnoredActor(Driver);
    if (!GetWorld()->OverlapBlockingTestByProfile(Location, Turn.Quaternion(),
        Collision->GetCollisionProfileName(), FCollisionShape::MakeBox(HullExtent), Query))
    {
        Rotation = Turn;
    }

    FVector Target = Location + Rotation.Vector() * ForwardSpeed * Seconds;
    const FVector LeadingPoint = Target + Rotation.Vector() * FMath::Sign(ForwardSpeed) * 120.0;
    if (const TOptional<double> Floor = GroundHeight(*GetWorld(), LeadingPoint, Query);
        Floor.IsSet() && FMath::Abs(Floor.GetValue() + RideHeight - Location.Z) <= 65.0)
    {
        Target.Z = FMath::FInterpConstantTo(Location.Z, Floor.GetValue() + RideHeight,
            static_cast<double>(Seconds), 380.0);
    }
    else if (const TOptional<double> CenterFloor = GroundHeight(*GetWorld(), Target, Query);
        CenterFloor.IsSet() && FMath::Abs(CenterFloor.GetValue() + RideHeight - Location.Z) <= 65.0)
    {
        Target.Z = FMath::FInterpConstantTo(Location.Z, CenterFloor.GetValue() + RideHeight,
            static_cast<double>(Seconds), 380.0);
    }

    FHitResult Hit;
    SetActorLocationAndRotation(Target, Rotation, true, &Hit);
    if (Hit.bBlockingHit)
    {
        ForwardSpeed = 0.0f;
    }
}

void ABRVehicle::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!HasAuthority())
    {
        return;
    }
    if (!IsValid(Driver))
    {
        Driver = nullptr;
        ResetControls();
        return;
    }
    if (Driver->IsEliminated())
    {
        TryExit(Driver, true);
        return;
    }
    const ABRGameState* Match = GetWorld()->GetGameState<ABRGameState>();
    if (!Match || !Match->IsPlaying())
    {
        ResetControls();
        return;
    }
    if (GetWorld()->GetTimeSeconds() - LastDriveInputTime > 0.45)
    {
        DriveThrottle = 0.0f;
        DriveSteering = 0.0f;
        bDriveBrake = false;
    }
    Drive(FMath::Min(DeltaSeconds, 0.08f));
}
