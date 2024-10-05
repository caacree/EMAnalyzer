import SimpleITK as sitk
from mims.services.registration_utils import create_composite_mask
import os
from PIL import Image
from django.conf import settings

media_root = settings.MEDIA_ROOT


def command_iteration(method):
    """Callback invoked when the optimization has an iteration"""
    print(f"{method.GetOptimizerIteration():3} " + f"= {method.GetMetricValue():10.5f}")


def unwarp_image(mims_image):
    reg_loc = os.path.join(media_root, mims_image.file.path[:-3], "registration")

    # Read the fixed and moving images
    fixed_image = sitk.ReadImage(
        os.path.join(reg_loc, "em_reg_mask.tiff"), sitk.sitkFloat32
    )
    moving_image = sitk.ReadImage(
        os.path.join(reg_loc, "mims_reg_mask.tiff"), sitk.sitkFloat32
    )

    # Set up the BSpline transformation
    transformDomainMeshSize = [8] * moving_image.GetDimension()
    tx = sitk.BSplineTransformInitializer(fixed_image, transformDomainMeshSize)

    # Set up the image registration method
    registration = sitk.ImageRegistrationMethod()
    registration.SetMetricAsMeanSquares()
    registration.SetOptimizerAsLBFGSB(
        gradientConvergenceTolerance=1e-5,
        numberOfIterations=100,
        maximumNumberOfCorrections=5,
        maximumNumberOfFunctionEvaluations=1000,
        costFunctionConvergenceFactor=1e7,
    )
    registration.SetInitialTransform(tx, True)
    registration.SetInterpolator(sitk.sitkLinear)

    registration.AddCommand(
        sitk.sitkIterationEvent, lambda: command_iteration(registration)
    )

    outTx = registration.Execute(fixed_image, moving_image)
    print("-------")
    print(outTx)
    print(
        f"Optimizer stop condition: {registration.GetOptimizerStopConditionDescription()}"
    )
    print(f" Iteration: {registration.GetOptimizerIteration()}")
    print(f" Metric value: {registration.GetMetricValue()}")

    sitk.WriteTransform(outTx, os.path.join(reg_loc, "mims_transform.tfm"))

    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(fixed_image)
    resampler.SetInterpolator(sitk.sitkLinear)
    resampler.SetDefaultPixelValue(100)
    resampler.SetTransform(outTx)

    out = resampler.Execute(moving_image)
    simg1 = sitk.Cast(sitk.RescaleIntensity(fixed_image), sitk.sitkUInt8)
    simg2 = sitk.Cast(sitk.RescaleIntensity(out), sitk.sitkUInt8)
    # cimg = sitk.Compose(simg1, simg2, simg1 // 2.0 + simg2 // 2.0)
    sitk.WriteImage(simg2, os.path.join(reg_loc, "mims_mask_unwarped.tif"))
    unwarped_composite = create_composite_mask(
        sitk.GetArrayFromImage(simg1), sitk.GetArrayFromImage(simg2)
    )
    Image.fromarray(unwarped_composite).save(
        os.path.join(reg_loc, "composite_mask_unwarped.png")
    )
    return
