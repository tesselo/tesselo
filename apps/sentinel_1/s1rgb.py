import numpy

P1 = 10e-4
P2 = 0.0101
P3 = 0.0201
P4 = 0.0301
P5 = 0.04501
P6 = 0.0501
P7 = 0.901
P8 = 0.2501


def s1rgb(VV, VH, boost=True):
    """
    Convert VV and VH bands into false color RGB data.
    """
    if boost:
        red = P4 + numpy.log(
            P1 - numpy.log(P6 / (P3 + 2.5 * VV)) + numpy.log(P6 / (P3 + 1.5 * VH))
        )
        green = P6 + numpy.exp(P8 * (numpy.log(P2 + 2 * VV) + numpy.log(P3 + 7 * VH)))
        blue = 0.8 - numpy.log(P6 / (P5 - P7 * VV))
    else:
        red = P4 + numpy.log(P1 - numpy.log(P6 / (P3 + 2 * VV)))
        green = P6 + numpy.exp(P8 * (numpy.log(P2 + 2 * VV) + numpy.log(P3 + 5 * VH)))
        blue = 1 - numpy.log(P6 / (P5 - P7 * VV))

    return (red, green, blue)
