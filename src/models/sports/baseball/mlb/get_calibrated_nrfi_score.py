import math


def p_nrfi(score):
    return 1 / (1 + math.exp(-(0.8780 - 0.0270 * score)))
