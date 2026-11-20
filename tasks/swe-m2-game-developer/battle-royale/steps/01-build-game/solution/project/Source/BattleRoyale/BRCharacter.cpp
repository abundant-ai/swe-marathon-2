#include "BRCharacter.h"

#include "BRLoot.h"
#include "BRMatch.h"
#include "BRVehicle.h"
#include "BRWeaponRules.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Net/UnrealNetwork.h"
#include "Sound/SoundWaveProcedural.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
using BRWeapon::FRifleTuning;
constexpr float FullHealth = 100.0f;
constexpr float WalkSpeed = 460.0f;
constexpr float SprintSpeed = 680.0f;
constexpr float AimSpeed = 275.0f;
constexpr float EquipSeconds = 0.28f;
constexpr float ShotRange = 10500.0f;
constexpr float ThirdPersonArmLength = 340.0f;
constexpr float ThirdPersonFieldOfView = 87.0f;
const FVector ThirdPersonSocketOffset(0.0, 54.0, 12.0);

/** Select the fictional balance values for a rifle already chosen by the caller. */
const FRifleTuning& Tuning(EBRRifle Rifle)
{
    return Rifle == EBRRifle::AK47 ? BRWeapon::AK : BRWeapon::M16;
}

/** Apply the engine's basic-shape color parameter to one visual mesh. */
void Tint(UStaticMeshComponent* Part, const FLinearColor& Color)
{
    if (UMaterialInstanceDynamic* Material = Part->CreateDynamicMaterialInstance(0))
    {
        Material->SetVectorParameterValue(TEXT("Color"), Color);
    }
}

/** Play an original, short arcade shot sound synthesized into mono PCM. */
void PlayShotSound(ABRCharacter* Player, const FVector& Position, bool bAutomatic)
{
    constexpr int32 Rate = 22050;
    constexpr int32 Samples = Rate / 9;
    TArray<int16> PCM;
    PCM.SetNumUninitialized(Samples);
    uint32 Seed = bAutomatic ? 151u : 241u;
    const float Tone = bAutomatic ? 105.0f : 158.0f;
    for (int32 Index = 0; Index < Samples; ++Index)
    {
        Seed = 1664525u * Seed + 1013904223u;
        const float Noise = static_cast<float>(Seed >> 16) / 32768.0f - 1.0f;
        const float Seconds = static_cast<float>(Index) / Rate;
        const float Pulse = 0.7f * Noise + 0.3f * FMath::Sin(2.0f * PI * Tone * Seconds);
        PCM[Index] = static_cast<int16>(FMath::RoundToInt(22500.0f * Pulse * FMath::Exp(-36.0f * Seconds)));
    }
    USoundWaveProcedural* Wave = NewObject<USoundWaveProcedural>(Player);
    Wave->NumChannels = 1;
    Wave->SetSampleRate(Rate, false);
    Wave->Duration = static_cast<float>(Samples) / Rate;
    Wave->bLooping = false;
    Wave->QueueAudio(reinterpret_cast<const uint8*>(PCM.GetData()), PCM.Num() * sizeof(int16));
    UGameplayStatics::PlaySoundAtLocation(Player, Wave, Position, 0.32f);
}
}

ABRCharacter::ABRCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    bReplicates = true;
    SetReplicateMovement(true);
    GetCapsuleComponent()->InitCapsuleSize(42.0f, 94.0f);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    bUseControllerRotationYaw = true;
    BaseEyeHeight = 62.0f;
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->bOrientRotationToMovement = false;
    Movement->MaxWalkSpeed = WalkSpeed;
    Movement->JumpZVelocity = 390.0f;
    Movement->AirControl = 0.31f;

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->bUsePawnControlRotation = true;
    CameraBoom->TargetArmLength = ThirdPersonArmLength;
    CameraBoom->TargetOffset = FVector(0, 0, BaseEyeHeight);
    CameraBoom->SocketOffset = ThirdPersonSocketOffset;
    CameraBoom->ProbeSize = 12.0f;
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("View"));
    Camera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    Camera->bUsePawnControlRotation = false;
    Camera->SetFieldOfView(ThirdPersonFieldOfView);

    Model = CreateDefaultSubobject<USceneComponent>(TEXT("Model"));
    Model->SetupAttachment(RootComponent);
    Weapon = CreateDefaultSubobject<USceneComponent>(TEXT("Weapon"));
    Weapon->SetupAttachment(Model);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BaseMaterial(
        TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));

    // Each default mesh has a stable name and contributes to a hand-built geometric silhouette.
    auto CreatePart = [this](const TCHAR* Name, USceneComponent* Parent, UStaticMesh* Shape,
        const FVector& Location, const FVector& Scale) -> UStaticMeshComponent*
    {
        UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Name);
        Part->SetupAttachment(Parent);
        Part->SetStaticMesh(Shape);
        Part->SetMaterial(0, BaseMaterial.Object);
        Part->SetRelativeLocation(Location);
        Part->SetRelativeScale3D(Scale);
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetGenerateOverlapEvents(false);
        return Part;
    };

    BodyMeshes.Add(CreatePart(TEXT("Torso"), Model, Cube.Object, FVector(0, 0, 24), FVector(.30, .55, .62)));
    BodyMeshes.Add(CreatePart(TEXT("Vest"), Model, Cube.Object, FVector(12, 0, 30), FVector(.15, .57, .47)));
    BodyMeshes.Add(CreatePart(TEXT("Head"), Model, Sphere.Object, FVector(0, 0, 71), FVector(.28, .27, .30)));
    BodyMeshes.Add(CreatePart(TEXT("Cap"), Model, Sphere.Object, FVector(-1, 0, 82), FVector(.31, .30, .16)));
    BodyMeshes.Add(CreatePart(TEXT("LeftArm"), Model, Sphere.Object,
        FVector(9, -34, 21), FVector(.16, .18, .48)));
    BodyMeshes.Add(CreatePart(TEXT("RightArm"), Model, Sphere.Object, FVector(10, 34, 21), FVector(.16, .18, .48)));
    LeftLeg = CreatePart(TEXT("LeftLeg"), Model, Cube.Object, FVector(0, -14, -48), FVector(.22, .22, .83));
    RightLeg = CreatePart(TEXT("RightLeg"), Model, Cube.Object, FVector(0, 14, -48), FVector(.22, .22, .83));
    BodyMeshes.Add(LeftLeg);
    BodyMeshes.Add(RightLeg);

    WeaponMeshes.Add(CreatePart(TEXT("Receiver"), Weapon, Cube.Object, FVector(18, 0, 0), FVector(.43, .075, .10)));
    WeaponMeshes.Add(CreatePart(TEXT("Handguard"), Weapon, Cube.Object, FVector(49, 0, 0), FVector(.25, .085, .085)));
    WeaponMeshes.Add(CreatePart(TEXT("Barrel"), Weapon, Cube.Object, FVector(65, 0, 1), FVector(.24, .035, .035)));
    WeaponMeshes.Add(CreatePart(TEXT("Stock"), Weapon, Cube.Object, FVector(-16, 0, 0), FVector(.25, .075, .095)));
    WeaponMeshes.Add(CreatePart(TEXT("Magazine"), Weapon, Cube.Object, FVector(10, 0, -11), FVector(.09, .07, .17)));
    WeaponMeshes.Add(CreatePart(TEXT("RearSight"), Weapon, Cube.Object, FVector(1, 0, 8), FVector(.025, .035, .07)));
    WeaponMeshes.Add(CreatePart(TEXT("FrontSight"), Weapon, Cube.Object, FVector(60, 0, 8), FVector(.025, .030, .07)));
    MuzzleFlash = CreateDefaultSubobject<UPointLightComponent>(TEXT("MuzzleFlash"));
    MuzzleFlash->SetupAttachment(Weapon);
    MuzzleFlash->SetRelativeLocation(FVector(78, 0, 2));
    MuzzleFlash->SetLightColor(FLinearColor(1.0f, .48f, .12f));
    MuzzleFlash->SetIntensity(1400.0f);
    MuzzleFlash->SetAttenuationRadius(270.0f);
    MuzzleFlash->SetCastShadows(false);
    MuzzleFlash->SetVisibility(false);

    SurfaceImpact = CreatePart(TEXT("SurfaceImpact"), RootComponent, Sphere.Object,
        FVector::ZeroVector, FVector(.14));
    SurfaceImpact->SetAbsolute(true, true, true);
    SurfaceImpact->SetCastShadow(false);
    SurfaceImpactLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("SurfaceImpactLight"));
    SurfaceImpactLight->SetupAttachment(SurfaceImpact);
    SurfaceImpactLight->SetAbsolute(true, true, true);
    SurfaceImpactLight->SetMobility(EComponentMobility::Movable);
    SurfaceImpactLight->SetLightColor(FLinearColor(1.0f, .28f, .05f));
    SurfaceImpactLight->SetIntensity(1600.0f);
    SurfaceImpactLight->SetAttenuationRadius(45.0f);
    SurfaceImpactLight->SetCastShadows(true);
    SurfaceImpactLight->SetVisibility(false);
    SurfaceImpact->SetVisibility(false);
}

void ABRCharacter::BeginPlay()
{
    Super::BeginPlay();
    CameraBoom->AddTickPrerequisiteActor(this);
    const FLinearColor Jacket(.085f, .15f, .12f);
    const FLinearColor Vest(.20f, .16f, .09f);
    const FLinearColor Face(.43f, .26f, .16f);
    const FLinearColor Trousers(.12f, .14f, .13f);
    const FLinearColor Palette[] = {Jacket, Vest, Face, Jacket, Jacket, Jacket, Trousers, Trousers};
    for (int32 Index = 0; Index < BodyMeshes.Num(); ++Index)
    {
        Tint(BodyMeshes[Index], Palette[Index]);
    }
    Tint(SurfaceImpact, FLinearColor(1.0f, .43f, .08f));
    OnRep_Health();
}

void ABRCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABRCharacter, Health);
    DOREPLIFETIME(ABRCharacter, EquippedRifle);
    DOREPLIFETIME(ABRCharacter, ReloadEndTime);
    DOREPLIFETIME(ABRCharacter, bSprinting);
    DOREPLIFETIME(ABRCharacter, bAiming);
    DOREPLIFETIME(ABRCharacter, RecoilPeak);
    DOREPLIFETIME(ABRCharacter, LastRecoilShotTime);
    DOREPLIFETIME(ABRCharacter, Vehicle);
    DOREPLIFETIME_CONDITION(ABRCharacter, bOwnsAK47, COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(ABRCharacter, bOwnsM16, COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(ABRCharacter, AKLoaded, COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(ABRCharacter, M16Loaded, COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(ABRCharacter, AKReserve, COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(ABRCharacter, M16Reserve, COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(ABRCharacter, ActionFeedback, COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(ABRCharacter, FeedbackEndTime, COND_OwnerOnly);
}

void ABRCharacter::ResetForMatch()
{
    if (!HasAuthority())
    {
        return;
    }
    if (ABRVehicle* Car = GetVehicle())
    {
        Car->TryExit(this, true);
    }
    SetVehicle(nullptr);
    Health = FullHealth;
    AKLoaded = AKReserve = M16Loaded = M16Reserve = 0;
    bOwnsAK47 = bOwnsM16 = bSprinting = bAiming = bBraking = false;
    bTriggerHeld = false;
    EquippedRifle = EBRRifle::None;
    NextShotTime = EquipReadyTime = NextInteractionTime = 0.0f;
    RecoilPeak = LastRecoilShotTime = 0.0f;
    SurfaceImpactEndTime = 0.0f;
    SurfaceImpact->SetVisibility(false, true);
    CancelWeaponActions();
    ActionFeedback.Reset();
    FeedbackEndTime = 0.0f;
    SetActorRotation(FRotator(0.0, GetActorRotation().Yaw, 0.0));
    GetCharacterMovement()->StopMovementImmediately();
    OnRep_Health();
    ForceNetUpdate();
}

void ABRCharacter::ApplyAuthorityDamage(float Damage)
{
    if (!HasAuthority() || !CanPlay() || !FMath::IsFinite(Damage) || Damage <= 0.0f)
    {
        return;
    }
    Health = FMath::Max(0.0f, Health - Damage);
    SetActionFeedback(IsEliminated() ? TEXT("Eliminated") : TEXT("Taking damage"));
    if (IsEliminated())
    {
        CancelWeaponActions();
        bAiming = bSprinting = false;
        if (ABRVehicle* Car = GetVehicle())
        {
            Car->TryExit(this, true);
        }
        SetVehicle(nullptr);
        if (ABRGameMode* Mode = GetWorld()->GetAuthGameMode<ABRGameMode>())
        {
            Mode->NotifyElimination(this);
        }
    }
    OnRep_Health();
    ForceNetUpdate();
}

bool ABRCharacter::OwnsRifle(EBRRifle Rifle) const
{
    return Rifle == EBRRifle::AK47 ? bOwnsAK47 : Rifle == EBRRifle::M16 && bOwnsM16;
}

int32 ABRCharacter::GetLoadedAmmo(EBRRifle Rifle) const
{
    if (Rifle == EBRRifle::AK47) return AKLoaded;
    if (Rifle == EBRRifle::M16) return M16Loaded;
    return 0;
}

int32 ABRCharacter::GetReserveAmmo(EBRRifle Rifle) const
{
    if (Rifle == EBRRifle::AK47) return AKReserve;
    if (Rifle == EBRRifle::M16) return M16Reserve;
    return 0;
}

FString ABRCharacter::GetActionFeedback() const
{
    return MatchTime() < FeedbackEndTime ? ActionFeedback : FString();
}

ABRVehicle* ABRCharacter::GetVehicle() const
{
    return IsValid(Vehicle.Get()) ? Vehicle.Get() : nullptr;
}

void ABRCharacter::SetVehicle(ABRVehicle* NewVehicle)
{
    if (!HasAuthority() || Vehicle.Get() == NewVehicle)
    {
        return;
    }
    Vehicle = NewVehicle;
    CancelWeaponActions();
    bAiming = bSprinting = bBraking = false;
    DriveThrottle = DriveSteering = 0.0f;
    if (NewVehicle)
    {
        GetCharacterMovement()->StopMovementImmediately();
        GetCharacterMovement()->DisableMovement();
        AttachToComponent(NewVehicle->GetRootComponent(), FAttachmentTransformRules::SnapToTargetNotIncludingScale);
        SetActorRelativeLocation(NewVehicle->GetDriverSeatOffset());
    }
    else
    {
        DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
    }
    OnRep_Vehicle();
    ForceNetUpdate();
}

bool ABRCharacter::TryGiveItem(EBRItem Item, int32 Amount)
{
    if (!HasAuthority() || !CanPlay() || GetVehicle() || Amount <= 0)
    {
        return false;
    }
    if (Item == EBRItem::AK47 || Item == EBRItem::M16)
    {
        const bool bAK = Item == EBRItem::AK47;
        const EBRRifle Rifle = bAK ? EBRRifle::AK47 : EBRRifle::M16;
        bool& bOwns = bAK ? bOwnsAK47 : bOwnsM16;
        if (bOwns)
        {
            SetActionFeedback(TEXT("Already carrying this rifle"));
            return false;
        }
        bOwns = true;
        (bAK ? AKLoaded : M16Loaded) = Tuning(Rifle).Capacity;
        if (EquippedRifle == EBRRifle::None)
        {
            EquippedRifle = Rifle;
            EquipReadyTime = MatchTime() + EquipSeconds;
            OnRep_Equipped();
        }
        SetActionFeedback(bAK ? TEXT("Collected AK-47") : TEXT("Collected M16"));
    }
    else if (Item == EBRItem::AKAmmo || Item == EBRItem::M16Ammo)
    {
        int32& Reserve = Item == EBRItem::AKAmmo ? AKReserve : M16Reserve;
        if (Amount > MAX_int32 - Reserve)
        {
            return false;
        }
        Reserve += Amount;
        SetActionFeedback(TEXT("Collected reserve ammunition"));
    }
    else
    {
        return false;
    }
    ForceNetUpdate();
    return true;
}

bool ABRCharacter::CanPlay() const
{
    const ABRGameState* State = GetWorld() ? GetWorld()->GetGameState<ABRGameState>() : nullptr;
    return !IsEliminated() && State && State->IsPlaying();
}

float ABRCharacter::MatchTime() const
{
    if (const ABRGameState* State = GetWorld() ? GetWorld()->GetGameState<ABRGameState>() : nullptr)
    {
        return static_cast<float>(State->GetServerWorldTimeSeconds());
    }
    return GetWorld() ? static_cast<float>(GetWorld()->GetTimeSeconds()) : 0.0f;
}

void ABRCharacter::SetActionFeedback(const TCHAR* Text)
{
    ActionFeedback = Text;
    FeedbackEndTime = MatchTime() + 2.0f;
}

void ABRCharacter::CancelWeaponActions()
{
    bAutomaticFire = false;
    ReloadEndTime = 0.0f;
}

void ABRCharacter::OnRep_Health()
{
    RefreshMovement();
    Model->SetRelativeRotation(IsEliminated() ? FRotator(0.0, 0.0, 88.0) : FRotator::ZeroRotator);
    OnRep_Equipped();
}

void ABRCharacter::OnRep_Equipped()
{
    if (EquippedRifle == EBRRifle::None && !GetVehicle() && CameraBoom->TargetArmLength < ThirdPersonArmLength)
    {
        // The round reset reveals the body again, so restore the standing view immediately.
        CameraBoom->TargetArmLength = ThirdPersonArmLength;
        CameraBoom->SocketOffset = ThirdPersonSocketOffset;
        Camera->SetFieldOfView(ThirdPersonFieldOfView);
        Camera->SetRelativeRotation(FRotator::ZeroRotator);
    }
    const bool bAK = EquippedRifle == EBRRifle::AK47;
    Weapon->SetVisibility(!GetVehicle() && !IsEliminated() && EquippedRifle != EBRRifle::None, true);
    MuzzleFlash->SetVisibility(false);
    const FLinearColor Metal(.075f, .085f, .087f);
    const FLinearColor Furniture = bAK ? FLinearColor(.34f, .15f, .065f) : FLinearColor(.08f, .12f, .10f);
    for (int32 Index = 0; Index < WeaponMeshes.Num(); ++Index)
    {
        Tint(WeaponMeshes[Index], Index == 1 || Index == 3 ? Furniture : Metal);
    }
    WeaponMeshes[3]->SetRelativeScale3D(bAK ? FVector(.25, .075, .095) : FVector(.34, .065, .105));
    WeaponMeshes[4]->SetRelativeRotation(bAK ? FRotator(24, 0, 0) : FRotator(8, 0, 0));
}

void ABRCharacter::OnRep_Vehicle()
{
    Model->SetVisibility(!GetVehicle(), true);
    RefreshMovement();
    OnRep_Equipped();
}

void ABRCharacter::RefreshMovement()
{
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    const bool bMobile = !GetVehicle() && !IsEliminated();
    SetActorEnableCollision(bMobile);
    if (bMobile && Movement->MovementMode == MOVE_None)
    {
        Movement->SetMovementMode(MOVE_Walking);
    }
    else if (!bMobile)
    {
        Movement->StopMovementImmediately();
        Movement->DisableMovement();
    }
}

void ABRCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    GetCharacterMovement()->MaxWalkSpeed = bAiming ? AimSpeed : (bSprinting ? SprintSpeed : WalkSpeed);
    const float Now = MatchTime();
    if (HasAuthority())
    {
        if (IsReloading() && Now >= ReloadEndTime)
        {
            FinishReload();
        }
        if (bAutomaticFire && CanPlay() && Now >= NextShotTime)
        {
            TryFire();
        }
    }
    if (IsLocallyControlled() && GetVehicle() && CanPlay() && Now >= NextDriveTime)
    {
        NextDriveTime = Now + .07f;
        ServerDrive(DriveThrottle, DriveSteering, bBraking);
    }
    UpdatePresentation(DeltaSeconds);
}

void ABRCharacter::UpdatePresentation(float DeltaSeconds)
{
    const bool bMounted = GetVehicle() != nullptr;
    const bool bArmed = EquippedRifle != EBRRifle::None;
    const bool bScoped = bAiming && bArmed && !bMounted && !IsEliminated();
    const float ArmLength = bMounted ? 590.0f : (bScoped ? 7.0f : ThirdPersonArmLength);
    CameraBoom->TargetArmLength = FMath::FInterpTo(CameraBoom->TargetArmLength, ArmLength, DeltaSeconds, 13.0f);
    CameraBoom->SocketOffset = FMath::VInterpTo(CameraBoom->SocketOffset,
        bMounted ? FVector(0, 0, 88) : (bScoped ? FVector::ZeroVector : ThirdPersonSocketOffset), DeltaSeconds, 13.0f);
    Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView,
        bScoped ? 61.0f : ThirdPersonFieldOfView, DeltaSeconds, 13.0f));

    const float Stride = FMath::Clamp(static_cast<float>(GetVelocity().Size2D()) / WalkSpeed, 0.0f, 1.2f);
    GaitTime += DeltaSeconds * 11.0f * Stride;
    const float Swing = IsEliminated() || bMounted ? 0.0f : Stride * 22.0f * FMath::Sin(GaitTime);
    LeftLeg->SetRelativeRotation(FRotator(Swing, 0, 0));
    RightLeg->SetRelativeRotation(FRotator(-Swing, 0, 0));
    for (UStaticMeshComponent* Part : BodyMeshes)
    {
        Part->SetOwnerNoSee(bScoped);
    }

    float ReloadSway = 0.0f;
    if (IsReloading() && EquippedRifle != EBRRifle::None)
    {
        const float Progress = 1.0f - (ReloadEndTime - MatchTime()) / Tuning(EquippedRifle).ReloadSeconds;
        ReloadSway = FMath::Sin(PI * FMath::Clamp(Progress, 0.0f, 1.0f));
    }
    const double BasePitch = FRotator::NormalizeAxis(AimInputRotation().Pitch);
    const double Pitch = !bArmed || bMounted || IsEliminated() ? BasePitch : ShotAim(MatchTime()).Pitch;
    Camera->SetRelativeRotation(FRotator(Pitch - BasePitch, 0.0, 0.0));
    Weapon->SetRelativeLocation(bScoped && IsLocallyControlled() ? FVector(32, 0, 51) : FVector(27, 24, 28));
    Weapon->SetRelativeRotation(FRotator(Pitch - 38.0f * ReloadSway, 0.0f, 24.0f * ReloadSway));
    MuzzleFlash->SetVisibility(MatchTime() < FlashEndTime && !IsEliminated() && !bMounted);
    if (SurfaceImpactEndTime > 0.0f && MatchTime() >= SurfaceImpactEndTime)
    {
        SurfaceImpactEndTime = 0.0f;
        SurfaceImpact->SetVisibility(false, true);
    }
}

float ABRCharacter::RecoilAt(float Now) const
{
    return BRWeapon::RecoilAt(RecoilPeak, Now - LastRecoilShotTime);
}

FRotator ABRCharacter::AimInputRotation() const
{
    // The controller's aim precedes the recoil applied to the camera.
    const AController* AimController = GetController();
    return AimController ? AimController->GetControlRotation() : GetBaseAimRotation();
}

FRotator ABRCharacter::ShotAim(float Now) const
{
    FRotator Aim = AimInputRotation();
    Aim.Pitch = FMath::Clamp(FRotator::NormalizeAxis(Aim.Pitch) + RecoilAt(Now), -89.0, 89.0);
    return Aim;
}

void ABRCharacter::TryFire()
{
    const float Now = MatchTime();
    if (!CanPlay() || GetVehicle() || EquippedRifle == EBRRifle::None || IsReloading() || Now < EquipReadyTime)
    {
        bAutomaticFire = false;
        return;
    }
    if (Now < NextShotTime)
    {
        return;
    }
    int32& Loaded = EquippedRifle == EBRRifle::AK47 ? AKLoaded : M16Loaded;
    if (Loaded <= 0)
    {
        bAutomaticFire = false;
        SetActionFeedback(TEXT("Empty magazine. Reload."));
        return;
    }
    const FRifleTuning& Rifle = Tuning(EquippedRifle);
    --Loaded;
    NextShotTime = Now + Rifle.Interval;

    UWorld* World = GetWorld();
    const float Cone = FMath::DegreesToRadians(BRWeapon::SpreadDegrees(Rifle, bAiming));
    const FVector Direction = FMath::VRandCone(ShotAim(Now).Vector(), Cone);
    RecoilPeak = BRWeapon::RecoilAfterShot(RecoilAt(Now), Rifle, bAiming);
    LastRecoilShotTime = Now;
    const FVector AimOrigin = Camera->GetComponentLocation();
    const FVector Body = GetPawnViewLocation();
    const FVector Muzzle = Weapon->GetComponentTransform().TransformPosition(FVector(77, 0, 2));
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BRRifle), false, this);
    FHitResult ViewHit;
    FVector AimEnd = AimOrigin + Direction * ShotRange;
    if (World->LineTraceSingleByChannel(ViewHit, AimOrigin, AimEnd, ECC_Visibility, Query))
    {
        AimEnd = ViewHit.ImpactPoint + Direction * 10.0;
    }
    FHitResult ShotHit;
    const bool bMuzzleBlocked = World->LineTraceSingleByChannel(ShotHit, Body, Muzzle, ECC_Visibility, Query);
    const bool bHit = bMuzzleBlocked || World->LineTraceSingleByChannel(ShotHit, Muzzle, AimEnd, ECC_Visibility, Query);
    ABRCharacter* Opponent = bHit ? Cast<ABRCharacter>(ShotHit.GetActor()) : nullptr;
    const FVector SurfaceNormal = bHit && !Opponent ? FVector(ShotHit.ImpactNormal) : FVector::ZeroVector;
    if (Opponent)
    {
        if (!Opponent->IsEliminated())
        {
            Opponent->ApplyAuthorityDamage(Rifle.Damage);
            SetActionFeedback(TEXT("Hit confirmed"));
            UE_LOG(LogTemp, Display, TEXT("BR hit: %s -> %s, remaining health %.0f"),
                *GetName(), *Opponent->GetName(), Opponent->GetHealth());
        }
    }
    MulticastShot(FVector_NetQuantize(bMuzzleBlocked ? Body : Muzzle),
        FVector_NetQuantize(bHit ? FVector(ShotHit.ImpactPoint) : AimEnd), bHit,
        FVector_NetQuantizeNormal(SurfaceNormal), EquippedRifle);
    ForceNetUpdate();
}

void ABRCharacter::FinishReload()
{
    ReloadEndTime = 0.0f;
    if (!CanPlay() || GetVehicle() || !OwnsRifle(EquippedRifle))
    {
        return;
    }
    const bool bAK = EquippedRifle == EBRRifle::AK47;
    int32& Loaded = bAK ? AKLoaded : M16Loaded;
    int32& Reserve = bAK ? AKReserve : M16Reserve;
    const int32 Transfer = FMath::Min(Tuning(EquippedRifle).Capacity - Loaded, Reserve);
    Loaded += Transfer;
    Reserve -= Transfer;
    SetActionFeedback(TEXT("Reloaded"));
    ForceNetUpdate();
}

void ABRCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("MoveForward"), this, &ABRCharacter::MoveForward);
    Input->BindAxis(TEXT("MoveRight"), this, &ABRCharacter::MoveRight);
    Input->BindAxis(TEXT("Turn"), this, &ABRCharacter::LookYaw);
    Input->BindAxis(TEXT("LookUp"), this, &ABRCharacter::LookPitch);
    Input->BindAction(TEXT("Jump"), IE_Pressed, this, &ABRCharacter::StartJump);
    Input->BindAction(TEXT("Jump"), IE_Released, this, &ABRCharacter::EndJump);
    Input->BindAction(TEXT("Sprint"), IE_Pressed, this, &ABRCharacter::StartSprint);
    Input->BindAction(TEXT("Sprint"), IE_Released, this, &ABRCharacter::EndSprint);
    Input->BindAction(TEXT("Fire"), IE_Pressed, this, &ABRCharacter::StartFire);
    Input->BindAction(TEXT("Fire"), IE_Released, this, &ABRCharacter::EndFire);
    Input->BindAction(TEXT("Aim"), IE_Pressed, this, &ABRCharacter::StartAim);
    Input->BindAction(TEXT("Aim"), IE_Released, this, &ABRCharacter::EndAim);
    Input->BindAction(TEXT("Reload"), IE_Pressed, this, &ABRCharacter::RequestReload);
    Input->BindAction(TEXT("Rifle1"), IE_Pressed, this, &ABRCharacter::SelectAK47);
    Input->BindAction(TEXT("Rifle2"), IE_Pressed, this, &ABRCharacter::SelectM16);
    Input->BindAction(TEXT("Interact"), IE_Pressed, this, &ABRCharacter::RequestInteract);
    Input->BindAction(TEXT("Brake"), IE_Pressed, this, &ABRCharacter::StartBrake);
    Input->BindAction(TEXT("Brake"), IE_Released, this, &ABRCharacter::EndBrake);
}

void ABRCharacter::MoveForward(float Value)
{
    DriveThrottle = Value;
    if (CanPlay() && !GetVehicle()) AddMovementInput(GetActorForwardVector(), Value);
}

void ABRCharacter::MoveRight(float Value)
{
    DriveSteering = Value;
    if (CanPlay() && !GetVehicle()) AddMovementInput(GetActorRightVector(), Value);
}

void ABRCharacter::LookYaw(float Value) { AddControllerYawInput(Value); }
void ABRCharacter::LookPitch(float Value) { AddControllerPitchInput(Value); }
void ABRCharacter::StartJump() { if (CanPlay() && !GetVehicle()) Jump(); }
void ABRCharacter::EndJump() { StopJumping(); }
void ABRCharacter::StartSprint() { ServerSetSprint(true); }
void ABRCharacter::EndSprint() { ServerSetSprint(false); }
void ABRCharacter::StartFire() { ServerSetFire(true); }
void ABRCharacter::EndFire() { ServerSetFire(false); }
void ABRCharacter::StartAim() { ServerSetAim(true); }
void ABRCharacter::EndAim() { ServerSetAim(false); }
void ABRCharacter::RequestReload() { ServerReload(); }
void ABRCharacter::SelectAK47() { ServerEquip(EBRRifle::AK47); }
void ABRCharacter::SelectM16() { ServerEquip(EBRRifle::M16); }
void ABRCharacter::RequestInteract() { ServerInteract(); }
void ABRCharacter::StartBrake() { bBraking = true; }
void ABRCharacter::EndBrake() { bBraking = false; }

void ABRCharacter::ServerSetSprint_Implementation(bool bEnabled)
{
    bSprinting = bEnabled && CanPlay() && !GetVehicle();
}

void ABRCharacter::ServerSetFire_Implementation(bool bPressed)
{
    if (!bPressed)
    {
        bTriggerHeld = bAutomaticFire = false;
        return;
    }
    if (!CanPlay() || GetVehicle() || bTriggerHeld)
    {
        return;
    }
    bTriggerHeld = true;
    bAutomaticFire = EquippedRifle == EBRRifle::AK47;
    TryFire();
}

void ABRCharacter::ServerSetAim_Implementation(bool bEnabled)
{
    bAiming = bEnabled && CanPlay() && !GetVehicle() && EquippedRifle != EBRRifle::None;
}

void ABRCharacter::ServerEquip_Implementation(EBRRifle Rifle)
{
    if (!CanPlay() || GetVehicle() || !OwnsRifle(Rifle) || Rifle == EquippedRifle)
    {
        return;
    }
    CancelWeaponActions();
    EquippedRifle = Rifle;
    EquipReadyTime = MatchTime() + EquipSeconds;
    SetActionFeedback(Rifle == EBRRifle::AK47 ? TEXT("Equipped AK-47") : TEXT("Equipped M16"));
    OnRep_Equipped();
    ForceNetUpdate();
}

void ABRCharacter::ServerReload_Implementation()
{
    if (!CanPlay() || GetVehicle() || IsReloading() || !OwnsRifle(EquippedRifle) || MatchTime() < EquipReadyTime)
    {
        return;
    }
    if (GetLoadedAmmo(EquippedRifle) >= Tuning(EquippedRifle).Capacity || !GetReserveAmmo(EquippedRifle))
    {
        SetActionFeedback(TEXT("Magazine full or no compatible reserve ammunition"));
        return;
    }
    bAutomaticFire = false;
    ReloadEndTime = MatchTime() + Tuning(EquippedRifle).ReloadSeconds;
    SetActionFeedback(TEXT("Reloading"));
    ForceNetUpdate();
}

void ABRCharacter::ServerInteract_Implementation()
{
    if (!CanPlay() || MatchTime() < NextInteractionTime)
    {
        return;
    }
    NextInteractionTime = MatchTime() + .20f;
    if (ABRVehicle* Car = GetVehicle())
    {
        if (!Car->TryExit(this)) SetActionFeedback(TEXT("No room to exit"));
        return;
    }
    AActor* Target = nullptr;
    double BestDistance = TNumericLimits<double>::Max();
    const FVector Origin = GetActorLocation();
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(BRInteract), false, this);
    auto Consider = [this, &Target, &BestDistance, &Origin, &Query](AActor* Candidate, double MaximumRange)
    {
        const double Distance = FVector::DistSquared(Origin, Candidate->GetActorLocation());
        if (Distance >= BestDistance || Distance > FMath::Square(MaximumRange))
        {
            return;
        }
        FHitResult Obstruction;
        const bool bBlocked = GetWorld()->LineTraceSingleByChannel(Obstruction,
            GetPawnViewLocation(), Candidate->GetActorLocation(), ECC_Visibility, Query);
        if (!bBlocked || Obstruction.GetActor() == Candidate)
        {
            Target = Candidate;
            BestDistance = Distance;
        }
    };
    for (TActorIterator<ABRLoot> Loot(GetWorld()); Loot; ++Loot) Consider(*Loot, 260.0);
    for (TActorIterator<ABRVehicle> Car(GetWorld()); Car; ++Car) Consider(*Car, 350.0);
    if (ABRLoot* Loot = Cast<ABRLoot>(Target))
    {
        Loot->TryCollect(this);
    }
    else if (ABRVehicle* Car = Cast<ABRVehicle>(Target))
    {
        if (!Car->TryEnter(this)) SetActionFeedback(TEXT("Driver seat unavailable"));
    }
}

void ABRCharacter::ServerDrive_Implementation(float Throttle, float Steering, bool bBrake)
{
    if (ABRVehicle* Car = GetVehicle(); Car && CanPlay() && MatchTime() >= NextServerDriveTime)
    {
        if (FMath::IsFinite(Throttle) && FMath::IsFinite(Steering))
        {
            NextServerDriveTime = MatchTime() + .04f;
            Car->SetDriveInput(this, FMath::Clamp(Throttle, -1.0f, 1.0f), FMath::Clamp(Steering, -1.0f, 1.0f), bBrake);
        }
    }
}

void ABRCharacter::MulticastShot_Implementation(
    FVector_NetQuantize Origin, FVector_NetQuantize End, bool bHit,
    FVector_NetQuantizeNormal SurfaceNormal, EBRRifle Rifle)
{
    if (GetNetMode() == NM_DedicatedServer)
    {
        return;
    }
    FlashEndTime = MatchTime() + .065f;
    MuzzleFlash->SetVisibility(true);
    DrawDebugLine(GetWorld(), Origin, End, FColor(255, 209, 113), false, .047f, 0, 1.7f);
    if (!SurfaceNormal.IsNearlyZero())
    {
        // Shift the effect off the surface so scene depth can occlude it naturally.
        const FVector FlashLocation = End + SurfaceNormal * 9.0;
        SurfaceImpact->SetWorldLocation(FlashLocation);
        SurfaceImpactLight->SetWorldLocation(End + SurfaceNormal * 24.0);
        SurfaceImpactEndTime = MatchTime() + .30f;
        SurfaceImpact->SetVisibility(true, true);
    }
    else if (bHit)
    {
        DrawDebugPoint(GetWorld(), End, 9.0f, FColor(251, 176, 62), false, .16f);
    }
    PlayShotSound(this, Origin, Rifle == EBRRifle::AK47);
}
