import torch
import matplotlib.pyplot as plt, seaborn as sns, pandas as pd
import numpy as np
import os, sys, math
from nibabel.viewers import OrthoSlicer3D as ov
import torchio as tio
from utils_file import gfile, get_parent_path
sns.set(style="whitegrid")
pd.set_option('display.max_rows', None, 'display.max_columns', None, 'display.max_colwidth', -1, 'display.width', 400)


def corrupt_data( x0, sigma= 5, amplitude=20, method='gauss', mvt_axes=[1], center='zero' ):
    fp = np.zeros((6, 200))
    x = np.arange(0, 200)
    if method=='gauss':
        y = np.exp(-(x - x0) ** 2 / float(2 * sigma ** 2))*amplitude
    elif method == 'step':
        if x0 < 100:
            y = np.hstack((np.zeros((1, (x0 - sigma))),
                           np.linspace(0, amplitude, 2 * sigma + 1).reshape(1, -1),
                           np.ones((1, ((200 - x0) - sigma - 1))) * amplitude))
        else:
            y = np.hstack((np.zeros((1, (x0 - sigma))),
                           np.linspace(0, -amplitude, 2 * sigma + 1).reshape(1, -1),
                           np.ones((1, ((200 - x0) - sigma - 1))) * -amplitude))
        y = y[0]
    elif method == 'Ustep':
        y = np.zeros(200)
        y[x0-(sigma//2):x0+(sigma//2)] = 1
    elif method == 'sin':
        #fp = np.zeros((6, 182*218))
        #x = np.arange(0,182*218)
        y = np.sin(x/x0 * 2 * np.pi)
        #plt.plot(x,y)
    if center=='zero':
        print(y.shape)
        y = y -y[100]
    for xx in mvt_axes:
        fp[xx,:] = y
    return y

def _translate_freq_domain( freq_domain, translations, inv_transfo=False):
    translations = -translations if inv_transfo else translations

    lin_spaces = [np.linspace(-0.5, 0.5, x) for x in freq_domain.shape] #todo it suposes 1 vox = 1mm
    meshgrids = np.meshgrid(*lin_spaces, indexing='ij')
    grid_coords = np.array([mg.flatten() for mg in meshgrids])

    phase_shift = np.multiply(grid_coords, translations).sum(axis=0)  # phase shift is added
    exp_phase_shift = np.exp(-2j * math.pi * phase_shift)
    freq_domain_translated = exp_phase_shift * freq_domain.reshape(-1)

    return freq_domain_translated.reshape(freq_domain.shape)
def print_fft(Fi):
    s1 = np.sum(np.imag(Fi[0:100]))
    s2 = np.sum(np.imag(Fi[101:]))
    print('ks1 {} ks2 {} ks1+ks2 {} sum {}'.format(s1,s2,s1+s2,np.sum(np.imag(Fi))))
    s1 = np.sum(Fi[0:100])
    s2 = np.sum(Fi[101:])
    print('ks1 {} ks2 {} ks1+ks2 {} sum {}'.format(s1,s2,s1+s2,np.sum(Fi)))

def sym_imag(Fi, Fo=None):
    lin_spaces = [np.linspace(-0.5, 0.5, x) for x in Fi.shape] #todo it suposes 1 vox = 1mm
    meshgrids = np.meshgrid(*lin_spaces, indexing='ij')
    grid_coords = np.array([mg.flatten() for mg in meshgrids])
    sum_list=[]
    sum_ini = np.sum(np.imag(Fi[0:100])) + np.sum(np.imag(Fi[101:]));
    print(f'sum_ini is {sum_ini}, ')
    resolution=1000
    xx = np.arange(-30000,30000)
    for i in xx:
        t1 = np.ones(200) * i /resolution
        t2 = np.ones(200) * (i+1)/resolution
        phase_shift1 = np.multiply(grid_coords, t1).sum(axis=0)  # phase shift is added
        phase_shift2 = np.multiply(grid_coords, t2).sum(axis=0)  # phase shift is added
        exp_phase_shift1 = np.exp(-2j * math.pi * phase_shift1)
        exp_phase_shift2 = np.exp(-2j * math.pi * phase_shift2)
        #exp_phase_shift1 = np.exp(-2j * math.pi * i/4000)
        Fit1 = exp_phase_shift1 * Fi
        Fit2 = exp_phase_shift2 * Fi
        s1 = np.sum(np.imag(Fit1[0:100])) + np.sum(np.imag(Fit1[101:]));
        s2 = np.sum(np.imag(Fit2[0:100])) + np.sum(np.imag(Fit2[101:]));
        sum_list.append(s1)
        #s2 = np.sum(np.imag(Fit2)) #marche pas pour sinus
        #print(f's1 {s1} s2 {s2}')
        if s2*s1 <0 :#or s1*s2 < 1e-4:
            if np.abs(s1) < np.abs(s2):
                Fmin = Fit1; phase_shift = 1/resolution #phase_shift1
            else:
                Fmin = Fit2; phase_shift = (i+1)/resolution #phase_shift2
            print_fft(Fmin)
            print(f'phase shift {phase_shift}')
            xx = xx / resolution
            plt.figure();
            plt.plot(xx[0:len(sum_list)], sum_list)
            return Fmin
    print('warning no change of sign')
    xx = xx/resolution
    plt.figure();plt.plot(xx, sum_list)
    return Fi
#fmc = sym_imag(fm)

fpok = corrupt_data(100, sigma=20,center='zefro')
#fp = corrupt_data(90, sigma=20, method='step',center='zero')
so = corrupt_data(50,sigma=30, method='Ustep',center='None')
#so = corrupt_data(50,sigma=20, method='sin')+1
fi = np.fft.fftshift(np.fft.fftn(np.fft.ifftshift(so)).astype(np.complex))
#fm =_translate_freq_domain(fi, fp)

kx = np.arange(-1,1+2/200,2/(200-1))
fp = np.ones_like(kx)*1
fp = fpok
fp_kspace = np.exp(-1j * math.pi * kx * fp)
fp_im = np.fft.ifftshift(np.fft.ifftn(fp_kspace))
print_fft(fp_kspace)
fp_kspace = sym_imag(fp_kspace)

plt.figure(); plt.plot(np.imag(fp_kspace))

fm = fi * fp_kspace
som = np.fft.ifftshift(np.fft.ifftn(fm))

sconv_fft = np.fft.ifftshift(np.fft.ifftn(fi*fm))

plt.figure(); plt.plot(so); plt.plot(abs(som));
plt.figure();plt.plot(fp.T)
plt.figure(); plt.plot(np.real(fi)); plt.plot(np.imag(fi));plt.plot(np.real(fm)); plt.plot(np.imag(fm)); plt.legend(['Sr','Sim','Tr','Tim'])

#output = (np.fft.fftshift(np.fft.fftn(np.fft.ifftshift(image)))).astype(np.complex128)
siconv = np.convolve(so,so, mode='same')
soconv = np.abs(np.convolve(som, so, mode='same'))

plt.figure();plt.plot(siconv); plt.plot(soconv); plt.plot(np.abs(sconv_fft)); plt.legend(['auto','conv_img','conv_fft'])
