import matplotlib.pyplot as plt, pandas as pd, seaborn as sns
import torchio as tio, torch, time
from segmentation.config import Config
from segmentation.run_model import RunModel
from nibabel.viewers import OrthoSlicer3D as ov
import glob, os, numpy as np, pandas as pd, matplotlib.pyplot as plt, numpy.linalg as npl
import scipy.linalg as scl, scipy.stats as ss, quaternion as nq
from scipy.spatial import distance_matrix
from util_affine import perform_one_motion, product_dict, create_motion_job, select_data, corrupt_data, apply_motion, spm_matrix, spm_imatrix
from util_affine import get_in
import nibabel as nib
from read_csv_results import ModelCSVResults
from types import SimpleNamespace
from kymatio import HarmonicScattering3D
from types import SimpleNamespace
from script.create_jobs import create_jobs
import glob
from torchio.transforms.augmentation.intensity.random_motion_from_time_course import _interpolate_space_timing, _tile_params_to_volume_dims
import subprocess
from dual_quaternions import DualQuaternion
#np.set_printoptions(precision=2)
#pd.set_option('display.max_rows', None, 'display.max_columns', None, 'display.max_colwidth', -1, 'display.width', 400)

def change_root_path(f_path, root_path='/data/romain/PVsynth/motion_on_synth_data/delivery_new'):
    common_dir = os.path.basename(root_path)
    ss = f_path.split('/')
    for k,updir in enumerate(ss):
        if common_dir in updir:
            break
    snew = ss[k:]
    snew[0] = root_path
    return '/'.join(snew)
def get_sujname_from_path(ff):
    name = [];
    dn = os.path.dirname(ff)
    for k in range(3):
        name.append(os.path.basename(dn))
        dn = os.path.dirname(dn)
    return '_'.join(reversed(name))
def interpolate_fitpars(fpars, tr_fpars=None, tr_to_interpolate=2.4, len_output=250):
    fpars_length = fpars.shape[1]
    if tr_fpars is None: #case where fitpart where give as it in random motion (the all timecourse is fitted to kspace
        xp = np.linspace(0,1,fpars_length)
        x  = np.linspace(0,1,len_output)
    else:
        xp = np.asarray(range(fpars_length))*tr_fpars
        x = np.asarray(range(len_output))*tr_to_interpolate
    interpolated_fpars = np.asarray([np.interp(x, xp, fp) for fp in fpars])
    if xp[-1]<x[-1]:
        diff = x[-1] - xp[-1]
        npt_added = diff/tr_to_interpolate
        print(f'adding {npt_added:.1f}')
    return interpolated_fpars

dircati = '/data/romain/PVsynth/motion_on_synth_data/delivery_new'
fjson = '/data/romain/PVsynth/motion_on_synth_data/test1/main.json'
out_path = '/data/romain/PVsynth//motion_on_synth_data/fit_parmCATI_raw/'
out_path = '/data/romain/PVsynth/motion_on_synth_data/fsl_coreg_rot_trans_sigma_2-256_x0_256_suj_0'
out_path = '/data/romain/PVsynth/motion_on_synth_data/fsl_coreg_along_x0_rot_origY_suj_0'#fsl_coreg_along_x0_transXYZ_suj_0'

dircati = '/network/lustre/iss01/cenir/analyse/irm/users/ghiles.reguig/These/Dataset/cati_full/delivery_new/'
fjson = '/network/lustre/iss01/cenir/analyse/irm/users/romain.valabregue/PVsynth/job/motion/test1/main.json'
out_path = '/network/lustre/iss01/cenir/analyse/irm/users/romain.valabregue/PVsynth/job/motion/fit_parmCATI_raw/'
out_path = '/network/lustre/iss01/cenir/analyse/irm/users/romain.valabregue/PVsynth/job/motion/fsl_coreg_rot_trans_sigma_2-256_x0_256_suj_0/'
out_path = '/network/lustre/iss01/cenir/analyse/irm/users/romain.valabregue/PVsynth/job/motion/fsl_coreg_along_x0_transXYZ_suj_0'

import dill
#dill.dump_session('globalsave.pkl')
#dill.load_session('globalsave.pkl')

""" run motion """
allfitpars_preproc = glob.glob(dircati+'/*/*/*/*/fitpars_preproc.txt')
allfitpars_raw = glob.glob(dircati+'/*/*/*/*/fitpars.txt')
fp_paths = allfitpars_raw

fjson = '/data/romain/PVsynth/motion_on_synth_data/test1/main.json'
sdata, tmot, config_runner = select_data(fjson, param, to_canonical=False)
image = sdata.t1.data[0]
fi = (np.fft.fftshift(np.fft.fftn(np.fft.ifftshift(image)))).astype(np.complex128)

### ###### run motion on all fitpar
split_length = 10
create_motion_job(fp_paths, split_length, fjson, out_path, res_name='fit_parmCATI_raw', type='one_motion')
##############"


#read from global csv (to get TR)
dfall = pd.read_csv(dircati+'/description_copie.csv')
dfall['Fitpars_path'] = dfall['Fitpars_path'].apply(change_root_path)
dfall['resdir'] = dfall['Fitpars_path'].apply(get_sujname_from_path); dfall['resdir'] = out_path+dfall['resdir']

allfitpars_raw = dfall['Fitpars_path']
afffitpars_preproc = [os.path.basename(p) + '/fitpars_preproc.txt' for p in allfitpars_raw]
dfall = dfall.sort_values(by=['Fitpars_path'])

#read results
fcsv = glob.glob(out_path+'/*/*csv')
df = [pd.read_csv(ff) for ff in fcsv]
df1 = pd.concat(df, ignore_index=True); # dfall = df1
#df1['fp'] = df1['fp'].apply(change_root_path)

#for sigma fitpars
fp_paths = [os.path.dirname(ff)  + '/fitpars_orig.txt'  for ff in fcsv]
df1['fp'] = fp_paths

#df1['srot'] = abs(df1['shift_R1']) + abs(df1['shift_R2']) + abs(df1['shift_R3']);df1['stra'] = abs(df1['shift_T1']) + abs(df1['shift_T2']) + abs(df1['shift_T3'])
df_coreg=df1
df_coreg['stra'] = np.sqrt(abs(df_coreg['shift_0'])**2 + abs(df_coreg['shift_1'])**2 + abs(df_coreg['shift_2'])**2)
df_coreg['srot'] = np.sqrt(abs(df_coreg['shift_3'])**2 + abs(df_coreg['shift_4'])**2 + abs(df_coreg['shift_5'])**2)
#abs(df1['shift_3']) + abs(df1['shift_4']) + abs(df1['shift_5'])

df_coreg=df1.sort_values(by='fp')
df_coreg['TR'] = dfall['TR']
#no more use as concatenation is done in apply_motion
#df_coreg = df1[df1.flirt_coreg==1] ; df_coreg.index = range(len(df_coreg))
#df_nocoreg = df1[df1.flirt_coreg==0]; df_nocoreg.index = range(len(df_nocoreg))
#df_nocoreg.columns = ['noShift_' + k for k in  df_nocoreg.columns]
#df_coreg = pd.concat([df_coreg, df_nocoreg], sort=True, axis=1); del(df_nocoreg)


#add max amplitude and select data
for ii, fp_path in enumerate(df_coreg.fp.values):
    fitpar = np.loadtxt(fp_path)
    amplitude_max = fitpar.max(axis=1) - fitpar.min(axis=1)
    trans = npl.norm(fitpar[:3,:], axis=0); angle = npl.norm(fitpar[3:6,:], axis=0)
    for i in range(6):
        cname = f'amp_max{i}';        df_coreg.loc[ii, cname] = amplitude_max[i]
        cname = f'zero_shift{i}';        df_coreg.loc[ii, cname] = fitpar[i,fitpar.shape[1]//2]
        cname = f'mean_shift{i}';        df_coreg.loc[ii, cname] = np.mean(fitpar[i,:])

    #dd = distance_matrix(fitpar[:3,:].T, fitpar[:3,:].T)
    trans_diff = fitpar.T[:,None,:3] - fitpar.T[None,:,:3]  #numpy broadcating rule !
    dd = np.linalg.norm(trans_diff, axis=2)
    ddrot = np.linalg.norm(fitpar.T[:,None,3:] - fitpar.T[None,:,3:] , axis=-1)
    df_coreg.loc[ii, 'trans_max'] = dd.max(); df_coreg.loc[ii, 'rot_max'] = ddrot.max();
    df_coreg.loc[ii, 'amp_max_max'] = amplitude_max.max() #not very usefule (underestimation)

#get dual_quaternion description angle disp screw axis ...
ind_sel = df_coreg.amp_max_max>20
if 'suj_origin' in dir(): del (suj_origin);
dq_list = []
for ii, fp_path in enumerate(df_coreg.fp.values):
    #if not ind_sel[ii]:        continue
    print(ii)
    fitpar = np.loadtxt(fp_path)
    nbpts = fitpar.shape[1]
    thetas = np.zeros(nbpts); disp = np.zeros(nbpts); axiscrew = np.zeros((3,nbpts))
    line_distance = np.zeros(nbpts); origin_pts = np.zeros((3,nbpts))
    trans = np.zeros(nbpts);angle_sum = np.zeros(nbpts); one_sub_dq_list=[]
    q_dist_qr= np.ones(nbpts);q_dist_qd= np.zeros(nbpts);
    if 'dq_pre' in dir(): del(dq_pre)
    for nbt in range(nbpts):
        P = np.hstack([fitpar[:, nbt], [1, 1, 1, 0, 0, 0]])
        trans[nbt] = npl.norm(P[:3])
        angle_sum[nbt] = npl.norm(np.abs(P[3:6])) #too bad in maths : euler norm = teta ! but sometimes aa small shift
        aff = spm_matrix(P, order=1)
        dq = DualQuaternion.from_homogeneous_matrix(aff)
        one_sub_dq_list.append(dq)
        l, m, tt, dd = dq.screw(rtol=1e-5)

        thetas[nbt] = np.rad2deg(tt); disp[nbt] = abs(dd)
        if npl.norm(l)<1e-10:
            origin_pts[:,nbt] = [0, 0, 0]
        else:
            origin_pts[:,nbt] = np.cross(l,m)
        axiscrew[:,nbt] = l;   line_distance[nbt] = npl.norm(m)

        if 'dq_pre' not in dir():
            dq_pre=dq
        else:
            #lp, mp, ttp, ddp = dq.screw(rtol=1e-5)
            ttt = np.dot(dq.q_r.q, dq_pre.q_r.q) #dot product r* et r_pre
            q_dist_qr[nbt] = ttt #hmm ==1
            q_dist_qd[nbt] = (dq_pre*dq.inverse()).q_d.norm #not equal but same order as diff disp
            dq_pre = dq
    seuil_theta = 2
    if np.sum(thetas > seuil_theta)>0:
        if 'suj_origin' not in dir():
            sel_ind = thetas > seuil_theta
            suj_origin = origin_pts[:, sel_ind]
            suj_screew = axiscrew[:, sel_ind]
            ind_all_suj = np.ones_like(origin_pts[1, sel_ind])*ii
            keep_dq_list = list(np.array(one_sub_dq_list)[sel_ind])
        else:
            sel_ind = thetas > seuil_theta
            suj_origin = np.hstack((suj_origin,origin_pts[:, sel_ind]))
            suj_screew = np.hstack((suj_screew,axiscrew[:, sel_ind]))
            ind_all_suj = np.hstack((ind_all_suj, np.ones_like(origin_pts[1, sel_ind])*ii))
            keep_dq_list = list(np.array(one_sub_dq_list)[sel_ind])
        dq_list += keep_dq_list


    origin_diff1 = np.array([0]+[npl.norm(np.cross(origin_pts[:,nbt] ,origin_pts[:,nbt-1] ))/npl.norm(origin_pts[:,nbt]) for nbt in np.arange(1,nbpts)])
    origin_diff = origin_diff1 + np.array([0] + [npl.norm(np.cross(origin_pts[:,nbt] ,origin_pts[:,nbt+1] ))/npl.norm(origin_pts[:,nbt]) for nbt in np.arange(1,nbpts-1)]+[0])
    fig ,ax = plt.subplots(nrows=2,ncols=3)
    aa=ax[0,0]; aa.plot(origin_pts[1,:]); aa.set_ylabel('origin_pts Y');
    aa = ax[0, 1]; aa.plot(line_distance); aa.set_ylabel('line_dist');
    aa = ax[0, 2]; aa.plot(thetas); aa.set_ylabel('theta');aa.plot(angle_sum); aa.legend(['Theta','euler_sum']);
    aa = ax[1, 0]; aa.plot(disp); aa.set_ylabel('disp');aa.plot(trans); aa.legend(['Disp','trans_norm']);
    aa = ax[1, 1]; aa.plot(fitpar.T); aa.legend(range(6))
    aa = ax[1, 2]; aa.plot(origin_diff);


plt.figure();plt.plot(q_dist_qr); plt.plot(q_dist_qd)
plt.figure();plt.plot(disp, trans)
plt.figure(); plt.plot(angle_sum,thetas)
from mpl_toolkits import mplot3d

fig = plt.figure();ax = plt.axes(projection ='3d');plt.xlabel('x') ;plt.ylabel('y')
X, Y, Z = zip(*origin_pts.T); U,V,W = zip(*axiscrew.T*5)
ax.quiver(X, Y, Z, U, V, W)
fig = plt.figure();ax = plt.axes(projection ='3d');plt.xlabel('x') ;plt.ylabel('y')
ax.scatter(suj_origin[0,:],suj_origin[1,:],suj_origin[2,:])
fig ,ax = plt.subplots(nrows=2,ncols=2)
aa=ax[0,0]; aa.hist(suj_origin[0,:],bins=500); aa.set_ylabel('origin_pts X');aa.grid()
aa=ax[0,1]; aa.hist(suj_origin[1,:],bins=500); aa.set_ylabel('origin_pts Y');aa.grid()
aa=ax[1,0]; aa.hist(suj_origin[2,:],bins=500); aa.set_ylabel('origin_pts Z');aa.grid()
fig ,ax = plt.subplots(nrows=2,ncols=2)
aa=ax[0,0]; aa.hist(suj_screew[0,:],bins=500); aa.set_ylabel('suj_screew X');aa.grid()
aa=ax[0,1]; aa.hist(suj_screew[1,:],bins=500); aa.set_ylabel('suj_screew Y');aa.grid()
aa=ax[1,0]; aa.hist(suj_screew[2,:],bins=500); aa.set_ylabel('suj_screew Z');aa.grid()

df = pd.DataFrame()
dq_dict = [get_info_from_dq(dq) for dq in dq_list]
df = pd.DataFrame(dq_dict) #much faster than append in a for loop
fig ,ax = plt.subplots(nrows=2,ncols=2);
aa=ax[0,0]; aa.hist(df.trans.apply(lambda x: npl.norm(x)),bins=500); aa.set_ylabel('trans norm');aa.grid()
aa=ax[0,1]; aa.hist(df.theta,bins=500); aa.set_ylabel('theta');aa.grid()
aa=ax[1,0]; aa.hist(df.line_dist,bins=500); aa.set_ylabel('line_dist');aa.grid()
aa=ax[1,1]; aa.hist(df.disp,bins=500); aa.set_ylabel('disp');aa.grid()
fig.suptitle('40000 affine from CATI raw theta>2')

plt.plot(np.sort(df_coreg.amp_max_max));plt.grid()
df_coreg = df_coreg[ (df_coreg.amp_max_max>2) ];  df_coreg.index = range(len(df_coreg))

[tx,ty,tz,rx,ry,rz] = fitpar[:,110]
[tx,ty,tz,rx,ry,rz] = [0,0,0,10,15,20]
aff = spm_matrix([tx,ty,tz,rx,ry,rz,1,1,1,0,0,0],order=1)

# change aff_direct to have rotation expres at nifi origin
voxel_shift = [-100, -200, 50]
T = spm_matrix([voxel_shift[0], voxel_shift[1], voxel_shift[2], 0, 0, 0, 1, 1, 1, 0, 0, 0], order=4);
Ti = npl.inv(T)
aff_new = np.matmul(T, np.matmul(aff, Ti))
#aff_new = np.matmul(Ti, np.matmul(aff, T))

dq = DualQuaternion.from_homogeneous_matrix(aff_new)
l, m, tt, dd = dq.screw(rtol=1e-5)
np.cross(l,m)

rot = aff_new.copy(); offset = rot[:,3].copy(); offset[3]=0; rot[:,3] = [0, 0, 0, 1]
rr = np.eye(4) - rot
npl.pinv(rr).dot(offset)
#no single solution go to quaternion !


#Average fitpar
def average_affine(affine):
    q_list = [];    Aff_mean = np.zeros((4, 4))
    for aff in affine:
        q_list.append(nq.from_rotation_matrix(aff) )
        Aff_mean = Aff_mean + scl.logm(affine)
    #todo

def average_fitpar(fitpar, weights=None, average_exp_mat=True):
    q_list = []  #can't
    Aff_mean = np.zeros((4, 4))
    Aff_Euc_mean = np.zeros((3, 3))
    if weights is None:
        weights = np.ones(fitpar.shape[1])
    #normalize weigths
    weights = weights / np.sum(weights)

    dq_mean = DualQuaternion.identity()
    lin_fitpar = np.sum(fitpar*weights, axis=1)
    for nbt in range(fitpar.shape[1]):
        P = np.hstack([fitpar[:,nbt],[1,1,1,0,0,0]])
        affine = spm_matrix(P.copy(),order=0)  #order 0 to get the affine really applid in motion (change 1 to 0 01/04/21) it is is equivalent, since at the end we go back to euleur angle and trans...
        # new_q = nq.from_rotation_matrix(affine)
        # if 'previous_q' not in dir():
        #     previous_q = new_q
        # else:
        #     _ = nq.unflip_rotors([previous_q, new_q], inplace=True)
        #     previous_q = new_q
        #q_list.append( new_q  )
        Aff_Euc_mean = Aff_Euc_mean + weights[nbt] * affine[:3,:3]
        Aff_mean = Aff_mean + weights[nbt] * scl.logm(affine)
        dq = DualQuaternion.from_homogeneous_matrix(affine)
        #dq_mean = DualQuaternion.sclerp(dq, dq_mean, 1-(weights[nbt])/(1+weights[nbt]))
        dq_mean = DualQuaternion.sclerp(dq_mean, dq,(weights[nbt])/(1+weights[nbt]))

    Aff_mean = scl.expm(Aff_mean)
    wshift_exp = spm_imatrix(Aff_mean, order=0)[:6]

    #q_mean = nq.mean_rotor_in_chordal_metric(q_list)
    #Aff_q_rot = nq.as_rotation_matrix(q_mean)

    #Aff_q_rot = scl.polar(Aff_Euc_mean)[0]
    #Aff_q = np.eye(4)
    #Aff_q[:3,:3] = Aff_q_rot
    #wshift_quat = spm_imatrix(Aff_q, order=0)[:6]
    #wshift_quat[:3] = lin_fitpar[:3]
    wshift_quat = spm_imatrix(dq_mean.homogeneous_matrix(), order=0)[:6]

    return wshift_quat, wshift_exp, lin_fitpar

def average_fitpar_no_quaternion(fitpar, weights=None, average_exp_mat=True):
    Aff_mean = np.zeros((4, 4))
    if weights is None:
        weights = np.ones(fitpar.shape[1])
    #normalize weigths
    weights = weights / np.sum(weights)

    lin_fitpar = np.sum(fitpar*weights, axis=1)
    for nbt in range(fitpar.shape[1]):
        P = np.hstack([fitpar[:,nbt],[1,1,1,0,0,0]])
        affine = spm_matrix(P,order=1) #warning if not the one made by motion
        Aff_mean = Aff_mean + weights[nbt] * scl.logm(affine)

    Aff_mean = scl.expm(Aff_mean)
    wshift_exp = spm_imatrix(Aff_mean, order=1)[:6]

    return wshift_exp, lin_fitpar

#explore mean disp for different transform (select from frmi)
df = pd.DataFrame()
for dq in dq_list:
    aff = dq.homogeneous_matrix()
    disp_norm = get_dist_field(aff, list(image.shape))
    mean_disp = np.mean(disp_norm)
    wmean_disp = np.sum(disp_norm*image.numpy())/np.sum(image.numpy())
    dqmetric = get_info_from_dq(dq)
    dqmetric['mean_field_dis'] = mean_disp
    dqmetric['wmean_field_dis'] = wmean_disp
    dqmetric['trans_norm'] = npl.norm(aff[:3,3])
    df = df.append(dqmetric, ignore_index=True)

fig ,ax = plt.subplots(nrows=2,ncols=3)
aa=ax[0,0]; aa.scatter(df.mean_field_dis, df.disp); aa.set_ylabel('disp');aa.grid()
aa=ax[0,1]; aa.scatter(df.mean_field_dis, df.theta); aa.set_ylabel('theta');aa.grid()
aa=ax[0,2]; aa.scatter(df.mean_field_dis, df.line_dist); aa.set_ylabel('line dist');aa.grid()
aa=ax[1,0]; aa.scatter(df.mean_field_dis, df.line_dist*np.deg2rad(df.theta)+df.disp); aa.set_ylabel('line dist*theta/100 + disp');aa.grid()
aa=ax[1,1]; aa.scatter(df.mean_field_dis, (df.line_dist+100)*np.deg2rad(df.theta)+df.disp); aa.set_ylabel('line dist');aa.grid()
aa=ax[1,2]; aa.scatter(df.mean_field_dis, (df.line_dist+150)*np.deg2rad(df.theta)+df.disp); aa.set_ylabel('line dist');aa.grid()
severity = (df.line_dist.values+50)*np.deg2rad(df.theta.values)+df.disp.values
ind = (severity<42) & (severity>40)
imin, imax = df[ind].mean_field_dis.argmin(), df[ind].mean_field_dis.argmax()
index1, index2 = df[ind].index[imin], df[ind].index[imax]
df.loc[index1,:]
cmap = sns.color_palette("coolwarm", len(df)) #
cmap = sns.cubehelix_palette(as_cmap=True)
fig=plt.figure();ppp = plt.scatter(df.mean_field_dis, severity,c=df.line_dist, cmap=cmap); fig.colorbar(ppp), plt.grid()


#displacement quantification
#import SimpleITK as sitk #cant understand fucking convention with itk TransformToDisplacementField
def get_sphere_mask(image, radius=80):
    mask = np.zeros_like(image)
    (sx, sy, sz) = image.shape  # (64,64,64) #
    center = [sx // 2, sy // 2, sz // 2]

    [kx, ky, kz] = np.meshgrid(np.arange(0, sx, 1), np.arange(0, sy, 1), np.arange(0, sz, 1), indexing='ij')
    [kx, ky, kz] = [kx - center[0], ky - center[1], kz - center[2]]  # to simulate rotation around center
    ijk = np.stack([kx, ky, kz])
    dist_ijk = npl.norm(ijk,axis=0)
    mask[dist_ijk<radius] = 1
    return mask

def get_dist_field(affine, img_shape, return_vect_field=False, scale=None):

    (sx, sy, sz) = img_shape  # (64,64,64) #
    center = [sx // 2, sy // 2, sz // 2]

    [kx, ky, kz] = np.meshgrid(np.arange(0, sx, 1), np.arange(0, sy, 1), np.arange(0, sz, 1), indexing='ij')
    [kx, ky, kz] = [kx - center[0], ky - center[1], kz - center[2]]  # to simulate rotation around center
    ijk = np.stack([kx, ky, kz, np.ones_like(kx)])
    ijk_flat = ijk.reshape((4, -1))
    if scale is not None:
        sc_mat = np.eye(4) * scale; sc_mat[3,3] = 1
        affine = sc_mat.dot(affine)
    xyz_flat = affine.dot(ijk_flat)  # implicit convention reference center at 0,0,0
    if scale is None:
        disp_flat = xyz_flat - ijk_flat
    else:
        disp_flat = xyz_flat - ijk_flat*scale

    disp_norm = npl.norm(disp_flat[:3, :], axis=0)
    if return_vect_field:
        return disp_flat[:3, :].reshape([3] + img_shape)
    return disp_norm.reshape(img_shape)

def get_random_vec(range=[-1,1], size=3, normalize=False):
    res = np.random.uniform(low=range[0], high=range[1], size=size )
    if normalize:
        res = res/npl.norm(res)
    return res

def get_random_afine(angle=(2,10), trans=(0,0), origine=(80,100), mode='quat'):
    if mode == 'quat':
        theta = np.deg2rad(get_random_vec(angle,1)[0])
        l = get_random_vec(normalize=True);
        #orig = get_random_vec(normalize=True) * get_random_vec(origine,1)
        #m = np.cross(orig, l);
        #this does not work because only the projection of orig in the normal plan of l, is taken
        # so add the wanted distance from origine directly to m
        orig = get_random_vec(normalize=True)
        m = np.cross(orig, l)
        m = m / npl.norm(m) * get_random_vec(origine,1)
        disp = get_random_vec(trans,1)[0];
        #print(f'dual quat with l {l} m {m}  norm {npl.norm(m)} theta {np.rad2deg(theta)} disp {disp}')
        dq = DualQuaternion.from_screw(l, m, theta, disp)
        #get_info_from_dq(dq, verbose=True)
        aff = dq.homogeneous_matrix()
    if mode == 'euler':
        fp = np.ones(12); fp[9:]=0
        fp[3:6] = get_random_vec(angle,3)
        fp[:3] = get_random_vec(trans,3)
        #print(fp)
        aff = spm_matrix(fp, order=0)
    return(aff)

df = pd.DataFrame(); sphere_mask = get_sphere_mask(image)
for i in range(1000):
    res=dict()
    aff = get_random_afine(angle=(-20,20), trans=(-20,20), origine=(0,150), mode='quat')
    disp_norm = get_dist_field(aff, list(image.shape))
    #disp_norm_small = get_dist_field(aff, [22,26,22], scale=8)

    mean_disp = np.mean(disp_norm)
    wmean_disp = np.sum(disp_norm*image.numpy())/np.sum(image.numpy())
    wmean_disp_sphere = np.sum(disp_norm*sphere_mask)/np.sum(sphere_mask)
    res = dict(mean_disp=mean_disp, wmean_disp=wmean_disp,wmean_disp_sphere=wmean_disp_sphere, aff=aff)
    fp = spm_imatrix(aff, order=0)[:6]
    res['euler_trans'] = npl.norm(fp[:3])
    res['euler_rot'] = npl.norm(fp[3:])
    res['euler_fp'] = fp
    #fp = spm_imatrix(aff, order=1)[:6]  #the translation vector change, but the norm is the same !!!
    #res['euler1_trans'] = npl.norm(fp[:3])
    #res['euler1_rot'] = npl.norm(fp[3:])

    res = dict(get_info_from_dq(DualQuaternion.from_homogeneous_matrix(aff)), **res)
    df = df.append(res, ignore_index=True)


def compute_FD_P(fp):
    #https://github.com/FCP-INDI/C-PAC/blob/master/CPAC/generate_motion_statistics/generate_motion_statistics.py
    fd = np.sum(np.abs(fp[:3])) + (50 * np.pi/180) * np.sum(np.abs(fp[3:6]))
    return fd
def compute_FD_J(aff, rmax=80):
    M = aff - np.eye(4)
    A = M[0:3, 0:3]
    b = M[0:3, 3]   # np.sqrt(np.dot(b.T, b))  is the norm of translation vector
    fd = np.sqrt( (rmax * rmax / 5) * np.trace(np.dot(A.T, A)) + np.dot(b.T, b) )
    return fd
def compute_FD(x):
    trans = npl.norm(x['trans'])
    rot = x['theta']
    fd = trans + 80 / np.sqrt(1) * (np.pi/180) * rot
    return fd/2
def aff_trace(aff):
    M = aff -np.eye(4)
    A = M[0:3, 0:3]
    b = M[0:3, 3]
    #return np.sqrt(np.dot(b.T, b))
    return np.trace(np.dot(A.T, A))

df['traceT'] = df.aff.apply(lambda x: aff_trace(x))

df['fd_P'] = df.euler_fp.apply(lambda x : compute_FD_P(x) )
df['fd_J'] = df.aff.apply(lambda x : compute_FD_J(x) )
df['fd_R'] = df.apply(lambda x : compute_FD(x), axis=1)
x = df.wmean_disp_sphere # x = df.mean_disp
fig, axs = plt.subplots(nrows=2, ncols=2)
axs[0,0].scatter(x, df.fd_P); axs[0,0].grid(); axs[0,0].set_ylabel('df_P')
axs[0,1].scatter(x, df.fd_J); axs[0,1].grid(); axs[0,1].set_ylabel('df_J')
axs[1,0].scatter(x, df.fd_R); axs[1,0].grid(); axs[1,0].set_ylabel('df_R')

ind = (df.wmean_disp_sphere>29.5)&(df.wmean_disp_sphere<30.5)
dd = df.loc[ind,:]
aff0 = dd.iloc[dd.fd_J.argmin(),0]; dq0 = DualQuaternion.from_homogeneous_matrix(aff0)
aff1 = dd.iloc[dd.fd_J.argmax(),0]; dq1 = DualQuaternion.from_homogeneous_matrix(aff1)

orig =  np.vstack(df.l.values) # orig = np.vstack(df.origin_pts.values) orig = np.vstack(df.trans.values)
fig = plt.figure(); ax = plt.axes(projection ='3d')
ax.plot3D(orig[:,0], orig[:,1], orig[:,2],'ko');ax.set_ylabel('Oy');ax.set_xlabel('Ox');ax.set_zlabel('Oz')
plt.figure();plt.hist(df.euler_trans) #plt.hist(df.line_dist)# plt.hist(df.disp,bins=100)

plt.figure()
x = df.mean_disp
plt.scatter(x, df.trans.apply(lambda x: npl.norm(x)) ); plt.grid()
plt.scatter(x, df.theta ); plt.grid()
plt.scatter(x, (df.line_dist + 100) * np.deg2rad(df.theta) + df.trans.apply(lambda x: npl.norm(x)))


#let's do it directly
aff = spm_matrix([0,0,0,20,10,15,1,1,1,0,0,0],order=1)
aff_list=[]; #del(aff1)
angles = [25,25,25,25]; voxel_shifts = [[0,0,0], [-80,80,80], [8,-8,8], [80,-80,80]]
for angle,voxel_shift in zip(angles, voxel_shifts):
    aff = spm_matrix([0,0,0,angle/2,angle,angle,1,1,1,0,0,0],order=0)
    #voxel_shift = [8,8,8]
    T = spm_matrix([voxel_shift[0], voxel_shift[1], voxel_shift[2], 0, 0, 0, 1, 1, 1, 0, 0, 0], order=4);
    Ti = npl.inv(T)
    aff = np.matmul(T, np.matmul(aff, Ti))
    dq = DualQuaternion.from_homogeneous_matrix(aff)

    orig_pos = voxel_shift
    l = [0, 0, 1];    m = np.cross(orig_pos, l);
    theta = np.deg2rad(angle);    disp = 0;
    dq = DualQuaternion.from_screw(l, m, theta, disp)
    aff = dq.homogeneous_matrix()

    aff_list.append(aff)
    disp_norm = get_dist_field(aff, list(image.shape))
    disp_norm_small = get_dist_field(aff, [22,26,22], scale=8)

    mean_disp = np.mean(disp_norm)
    wmean_disp = np.sum(disp_norm*image.numpy())/np.sum(image.numpy())

    print(get_info_from_dq(dq))
    print(f'         mean disp is {mean_disp} weighted mean {wmean_disp}')

    do_plot=False
    if do_plot:
        [sx, sy, sz] = [32, 32, 32]
        disp_field = get_dist_field(aff,[32,32,32], return_vect_field=True)
        zslice=0
        vm = disp_field[:,:,:,zslice]
        [kx, ky, kz] = np.meshgrid(np.arange(0, sx, 1), np.arange(0, sy, 1), np.arange(0, sz, 1), indexing='ij')
        kxm, kym = kx[:,:,zslice], ky[:,:,zslice]
        plt.figure();plt.quiver(kxm, kym, vm[0,:,:],vm[1,:,:],width=0.001)

    dq = DualQuaternion.from_homogeneous_matrix(aff)
    l, m, tt, dd = dq.screw(rtol=1e-5)
    origin_pts = np.cross(l, m)
    X, Y, Z = origin_pts;    U, V, W = l*5;    ax.quiver(X, Y, Z, U, V, W)

fig = plt.figure();ax = plt.axes(projection ='3d');plt.xlabel('x') ;plt.ylabel('y')
origin_pts = np.cross(l,m)
X, Y, Z = origin_pts; U,V,W = l
ax.quiver(X, Y, Z, U, V, W)

import time
start=time.time()
fitpar=np.loadtxt(fp_path)
tmean, twImean = [], []
for nbt in range(fitpar.shape[1]):
    P = np.hstack([fitpar[:,nbt],[1,1,1,0,0,0]])
    aff = spm_matrix(P,order=1)
    disp_norm = get_dist_field(aff, list(image.shape))
    tmean.append(np.mean(disp_norm))
    twImean.append( np.sum(disp_norm * image.numpy()) / np.sum(image.numpy()) )

print(f'don in {time.time()-start} ')



#get the data
param = dict();param['suj_contrast'] = 1;param['suj_noise'] = 0.01;param['suj_index'] = 0;param['suj_deform'] = 0;param['displacement_shift_strategy']=None
sdata, tmot, config_runner = select_data(fjson, param, to_canonical=False)
image = sdata.t1.data[0]

fi = (np.fft.fftshift(np.fft.fftn(np.fft.ifftshift(image)))).astype(np.complex128)
#fi_phase = np.fft.fftshift(np.fft.fft(image, axis=1)) #do not show corectly in ov
fi_phase = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(image), axis=1)) #phase in y why it is the case in random_motion ?


#wcfft = abs(np.sum(np.sum(fi_phase,axis=0),axis=1))
wafft = abs(np.sum(np.sum(abs(fi_phase),axis=0),axis=1))
wa2fft = abs(np.sum(np.sum(abs(fi_phase**2),axis=0),axis=1))
coef_TF_3D = np.sum(abs(fi), axis=(0,2)) # easier to comute than with interval (but equivalent)
coef2_TF_3D = np.sum(abs(fi**2), axis=(0,2)) # this one is equivalent to wafft**2

w_coef_shaw = wafft/np.sum(wafft) #since it is equivalent
w_coef_short = coef_TF_3D/np.sum(coef_TF_3D)

#ov(abs(fi_phase))
ff_phase = np.sum(np.sum(abs(fi_phase),axis=0),axis=1)
# test different computation for the weigths
if False:
    fi_phase = np.fft.fftshift(np.fft.fft(np.fft.ifftshift(image), axis=1)) #phase in y why it is the case in random_motion ?
    center=[ii//2 for ii in fi_phase.shape]
    #fi_phase[:,:center[1],:] = 0;fi_phase[:,center[1]+1:,:] = 0
    fisum=np.zeros_like(image).astype(complex)
    wc,wa=np.zeros(fi_phase.shape[1]).astype(complex),np.zeros(fi_phase.shape[1])
    for x in range(fi_phase.shape[1]):
        fi_phase_cut = np.zeros_like(fi_phase).astype(complex)
        fi_phase_cut[:,x,:] = fi_phase[:,x,:]
        fi_image = np.fft.ifftshift(np.fft.ifft(np.fft.fftshift(fi_phase_cut), axis=1))
        fisum += fi_image # this reconstruct the image but not abs(fi_image)
        wc[x] = np.sum(fi_image*np.conj(fi_image)); wa[x] = np.sum(abs(fi_image))
        #ov(np.real(fi_image))

    ov(abs(fisum))

    plt.figure(); plt.plot(coef_TF_3D/np.sum(coef_TF_3D)) ; plt.plot(w_coef_short/np.sum(w_coef_short)) #ok
    plt.figure();plt.plot(w_coef_shaw/np.sum(w_coef_shaw));plt.plot(wafft/np.sum(wafft));plt.legend(['nfft','fft'])

    plt.figure(); plt.plot(coef_TF_3D**2/np.sum(coef_TF_3D**2)) ; plt.plot(w_coef_short**2/np.sum(w_coef_short**2)) #ok
    plt.figure();plt.plot(w_coef_shaw**2/np.sum(w_coef_shaw**2));plt.plot(wafft**2/np.sum(wafft**2));plt.legend(['nfft','fft'])
    plt.plot(coef2_TF_3D/np.sum(coef2_TF_3D))
    plt.plot(wa2fft/np.sum(wa2fft)) #that strange somme des carre ou carre de la somme , equivalent (after norm)

    plt.figure();plt.plot(abs(wc)/np.sum(abs(wc)));plt.plot(wa/np.sum(wa));plt.legend(['c','a'])
    plt.figure();plt.plot(abs(wc)/np.sum(abs(wc)));plt.plot(wa**2/np.sum(wa**2));plt.legend(['c','a'])
    plt.figure();plt.plot(abs(wcfft)/np.sum(abs(wcfft)));plt.plot(wafft/np.sum(wafft));plt.legend(['c','a'])
    #computing image power with 3D nftt or fft
    plt.figure();plt.plot(w_coef_shaw/np.sum(w_coef_shaw));plt.plot(wa/np.sum(wa));plt.legend(['nfft','fft'])
    plt.figure();plt.plot(w_coef_short/np.sum(w_coef_short));plt.plot(wafft/np.sum(wafft));plt.legend(['nfft','fft'])
    plt.figure();plt.plot(w_coef_TF2_short/np.sum(w_coef_TF2_short));plt.plot(wa2fft/np.sum(wa2fft));plt.legend(['nfft','fft'])
    plt.figure();plt.plot(wafft/np.sum(wafft));plt.plot(wa/np.sum(wa));plt.legend(['fft','fft_ima']) #identical

    ff_fi = np.sum(np.sum(abs(fi),axis=0),axis=1)
    plt.figure(); plt.plot(ff_phase/npl.sum(ff_phase)); plt.plot(ff_fi/npl.sum(ff_fi))

    fi_flat = np.reshape(np.transpose(fi,[0,2,1]),-1,order='F')


    #compute FFT weights for image (here always the same)
    w_coef = np.abs(fi)
    w_coef_flat = np.transpose(w_coef,[0,2,1]).reshape(-1, order='F') #ordering is important ! to the the phase in y !
    fitpar=interpolate_fitpars(fitpar,len_output=218)
    # w TF coef approximation at fitpar resolution (== assuming fitparinterp constant )
    w_coef_short, w_coef_TF2_short, w_coef_shaw = np.zeros_like(fitpar[0]), np.zeros_like(fitpar[0]), np.zeros_like(fitpar[0])
    step_size = w_coef_flat.shape[0] / w_coef_short.shape[0]
    for kk in range(w_coef_short.shape[0]):
        ind_start = int(kk * step_size)
        ind_end = ind_start + int(step_size)
        w_coef_short[kk] = np.sum(w_coef_flat[ind_start:ind_end])  # sum or mean is equivalent for the weighted mean
        w_coef_TF2_short[kk] = np.sum(w_coef_flat[ind_start:ind_end]**2)  # sum or mean is equivalent for the weighted mean

        # in shaw article, they sum the voxel in image domain (iFFT(im conv mask)) but 256 fft is too much time ...
        # fft_mask = np.zeros_like(w_coef_flat).astype(complex)
        # fft_mask[ind_start:ind_end] = w_coef_flat[ind_start:ind_end]
        # fft_mask = fft_mask.reshape(fi.shape, order='F')
        # ffimg = np.fft.ifftshift(np.fft.ifftn(fft_mask))
        # w_coef_shaw[kk] = np.sum(np.abs(ffimg))
        # to fix there is problem in th index that make if differ from wa following solution make it identical

        fft_mask = np.zeros_like(fi).astype(complex)
        fft_mask[:,kk,:] = fi[:,kk,:]
        ffimg = np.fft.ifftshift(np.fft.ifftn(fft_mask))
        w_coef_shaw[kk] = np.sum(np.abs(ffimg))

    w_coef_short = w_coef_short / np.sum(w_coef_short)  # nomalize the weigths
    w_coef_TF2_short = w_coef_TF2_short / np.sum(w_coef_TF2_short)  # nomalize the weigths
    w_coef_shaw = w_coef_shaw / np.sum(w_coef_shaw)  # nomalize the weigths
    plt.figure(); plt.plot(w_coef_short); plt.plot(w_coef_shaw); plt.plot(w_coef_TF2_short);
    plt.legend(['wTF', 'shaw', 'wTF2']) #but shaw method is identical to compute directly from 1D fft

#compute with different weigth on fipar
for ii, fp_path in enumerate(df_coreg.fp.values):
    fitpar = np.loadtxt(fp_path)
    if fitpar.shape[1] != w_coef_short.shape[0] :
        #fitparn = interpolate_fitpars(fitpar,df_coreg.loc[ii,'TR']/1000)  #no because randMotion did not consider a TR
        fitpar = interpolate_fitpars(fitpar, len_output=w_coef_short.shape[0])

    #fitparinter = _interpolate_space_timing(fitpar, 0.004, 2.3,[218, 182],0)
    #fitparinter = _tile_params_to_volume_dims(fitparinter, list(image.shape))

    w_quat, wshift, w_lin = average_fitpar(fitpar, w_coef_short)
    w_quat_shaw, wshift_shaw, w_lin_shaw = average_fitpar(fitpar, w_coef_shaw)
    w2_quat, w2shift, w2_lin = average_fitpar(fitpar, w_coef_short**2)
    w2_quat_shaw, w2shift_shaw, w2_lin_shaw = average_fitpar(fitpar, w_coef_shaw**2)


    print(f'suj {ii}  working on {fp_path}')
    for i in range(0, 6):
        #ffi = fitparinter[i].reshape(-1)
        #rrr = np.sum(ffi * w_coef_flat) / np.sum(w_coef_flat)
        #already sifted    rcheck2 = df_coreg.loc[ii,f'm_wTF_Disp_{i}']
        #rcheck = df_nocoreg.loc[ii,f'm_wTF_Disp_{i}']
        #print(f'n={i} mean disp {i} = {rrr}  / {rcheck} after shift {rcheck2}')
        #cname = f'before_coreg_wTF_Disp_{i}';        df_coreg.loc[ii, cname] = rrr

        rrr2 = np.sum(fitpar[i]*w_coef_short) #/ np.sum(w_coef_short)
        #fsl_shift = df_coreg.loc[ii, f'shift_T{i + 1}'] if i < 3 else df_coreg.loc[ii, f'shift_R{i - 2}']
        fsl_shift = 111#df_coreg.loc[ii, f'shift_{i}']
        #print(f'n={i} mean disp {i} (full/approx) = {rrr}  / {rrr2} after shift {rcheck2}')
        cname = f'before_coreg_short_wTF_Disp_{i}';        df_coreg.loc[ii, cname] = rrr2

        print(f'n={i} fsl shift {fsl_shift}  wTF shift {wshift[i]}  wshaw shift {wshift_shaw[i]}')
        #spm_imatrix(npl.inv(Aff_mean),order=0)
        cname = f'w_exp_TF_disp{i}';        df_coreg.loc[ii, cname] = wshift[i]
        cname = f'w_exp_shaw_disp{i}';        df_coreg.loc[ii, cname] = wshift_shaw[i]
        cname = f'w_quat_TF_disp{i}';        df_coreg.loc[ii, cname] = w_quat[i]
        cname = f'w_quat_shaw_disp{i}';        df_coreg.loc[ii, cname] = w_quat_shaw[i]
        cname = f'w_eul_TF_disp{i}';        df_coreg.loc[ii, cname] = w_lin[i]
        cname = f'w_eul_shaw_disp{i}';        df_coreg.loc[ii, cname] = w_lin_shaw[i]

        cname = f'w2_exp_TF_disp{i}';        df_coreg.loc[ii, cname] = w2shift[i]
        cname = f'w2_exp_shaw_disp{i}';        df_coreg.loc[ii, cname] = w2shift_shaw[i]
        cname = f'w2_quat_TF_disp{i}';        df_coreg.loc[ii, cname] = w2_quat[i]
        cname = f'w2_quat_shaw_disp{i}';        df_coreg.loc[ii, cname] = w2_quat_shaw[i]
        cname = f'w2_eul_TF_disp{i}';        df_coreg.loc[ii, cname] = w2_lin[i]
        cname = f'w2_eul_shaw_disp{i}';        df_coreg.loc[ii, cname] = w2_lin_shaw[i]


df_coreg.to_csv(out_path+'/df_coreg_fitparCATI_new_raw_sub.csv')
df_coreg.to_csv(out_path+'/df_coreg_fitpar_Sigmas_X256.csv')

#reasign each 6 disp key to rot_or rot vector
def disp_to_vect(s,key,type):
    if type=='rot':
        k1 = key[:-1] + '0'; k2 = key[:-1] + '1'; k3 = key[:-1] + '2';
    else:
        k1 = key[:-1] + '3'; k2 = key[:-1] + '4'; k3 = key[:-1] + '5';
    return np.array([s[k1], s[k2], s[k3]])

key_disp = [k for k in df_coreg.keys() if 'isp_1' in k]; key_replace_length = 7
key_disp = [k for k in df_coreg.keys() if 'isp1' in k]; key_replace_length = 6
key_disp = ['shift_0']; key_replace_length = 2
key_disp = [ 'zero_shift0', 'mean_shift4']; key_replace_length = 1
for k in key_disp:
    new_key = k[:-key_replace_length] +'_trans'
    df_coreg[new_key] = df_coreg.apply(lambda s: disp_to_vect(s, k, 'trans'), axis=1)
    new_key = k[:-key_replace_length] +'_rot'
    df_coreg[new_key] = df_coreg.apply(lambda s: disp_to_vect(s, k, 'rot'),  axis=1)
    for ii in range(6):
        key_del = f'{k[:-1]}{ii}';  del(df_coreg[key_del])

#same but with vector
#ynames=['w_exp_TF_trans','w_exp_shaw_trans','w_quat_TF_trans','w_quat_shaw_trans','w_eul_TF_trans','w_eul_shaw_trans']
ynames=['w_exp_TF_trans','w_exp_shaw_trans','w_eul_TF_trans','w_eul_shaw_trans']
ynames+=['w2_exp_TF_trans','w2_exp_shaw_trans','w2_eul_TF_trans','w2_eul_shaw_trans', 'zero_shift_trans', 'mean_shift_trans']
#ynames=['w_exp_TF_rot','w_exp_shaw_rot','w_quat_TF_rot','w_quat_shaw_rot','w_eul_TF_rot','w_eul_shaw_rot']
ynames+=['w_exp_TF_rot','w_exp_shaw_rot','w_eul_TF_rot','w_eul_shaw_rot']
ynames+=['w2_exp_TF_rot','w2_exp_shaw_rot','w2_eul_TF_rot','w2_eul_shaw_rot', 'zero_shift_rot', 'mean_shift_rot']
e_yname,d_yname=[],[]

e_yname += [f'error_{yy}' for yy in ynames ]
d_yname += [f'{yy}' for yy in ynames ]
for yname in ynames:
    xname ='shift_rot' if  'rot' in yname else 'shift_trans';
    x = df_coreg[f'{xname}'];  y = df_coreg[f'{yname}'];
    cname = f'error_{yname}';        df_coreg[cname] = (y-x).apply(lambda x: npl.norm(x))


dfm = df_coreg.melt(id_vars=['fp'], value_vars=e_yname, var_name='shift', value_name='error')
dfm["ei"] = 0
for kk in  dfm['shift'].unique() :
    dfm.loc[dfm['shift'] == kk, 'ei'] = 'trans' if 'trans' in kk else 'rot'  #int(kk[-1])
    dfm.loc[dfm['shift'] == kk, 'shift'] = kk[6:-6] if 'trans' in kk else kk[6:-4]
dfm.loc[dfm['shift'].str.contains('exp'),'interp'] = 'exp'
dfm.loc[dfm['shift'].str.contains('eul'),'interp'] = 'eul'
dfm.loc[dfm['shift'].str.contains('quat'),'interp'] = 'quat'
dfm.loc[dfm['shift'].str.contains('zero'),'interp'] = 'eul'
dfm.loc[dfm['shift'].str.contains('mean'),'interp'] = 'eul'
dfm['shift']=dfm['shift'].str.replace('_exp_','');dfm['shift']=dfm['shift'].str.replace('_eul_','')
dfm['shift']=dfm['shift'].str.replace('_quat_','');
#dfm['shift']=dfm['shift'].str.replace('zero_','');dfm['shift'] = dfm['shift'].str.replace('mean_', '')

sns.catplot(data=dfm,x='shift', y='error', col='ei',hue='interp', kind='strip', col_wrap=2, dodge=True)
sns.catplot(data=dfm,x='shift', y='error', col='ei',hue='interp', kind='boxen', col_wrap=2, dodge=True)
sns.pairplot(df1[sel_key], kind="scatter", corner=True)

#explore max error on CATI fit
df_coreg['error_w_exp_shaw_trans']
np.sort(df_coreg['error_w_exp_shaw_trans'].values)[::-1][:50]
ind_sel = np.argsort(df_coreg['error_w_exp_shaw_rot'].values)[::-1][:10]
for ii in ind_sel:
    print(f'loading {df_coreg.fp.values[ii]}')
    fitpar = np.loadtxt(df_coreg.fp.values[ii])
    fig=plt.figure()
    plt.plot(fitpar.T); plt.legend(['tx','ty','tz','rx','ry','rz']); plt.grid()
    center = fitpar.shape[1]//2
    ax=fig.get_axes()[0]; plt.plot([center, center], ax.get_ylim(),'k')
    perform_one_motion(df_coreg.fp.values[ii], fjson, fsl_coreg=True, return_motion=False, root_out_dir='/data/romain/PVsynth/motion_on_synth_data/fit_parmCATI_raw_saved')




for yname in ynames:
    #plot
    fig, axs = plt.subplots(nrows=2,ncols=3)
    max_errors=0
    for  i, ax in enumerate(axs.flatten()):
        #fsl_shift = df_coreg[ f'shift_T{i + 1}'] if i < 3 else df_coreg[ f'shift_R{i - 2}']
        fsl_shift =  df_coreg[ f'shift_{i}']
        xname ='shift_' #'before_coreg_short_wTF_Disp_'#'no_shift_wTF_Disp_' # 'w_expTF_disp' #'m_wTF2_Disp_' #
        #yname = 'w_quat_shaw_disp' #'no_shift_wTF2_Disp_' #'before_coreg_wTF_Disp_'  #
        #x = df_coreg[f'm_wTF2_Disp_{i}'] + fsl_shift
        #yname = 'no_shift_wTF2_Disp_'
        xname = 'w_exp_shaw_disp'
        yname = 'w_quat_shaw_disp'
        #x = fsl_shift if xname=='fsl_shift' else df_coreg[f'{xname}{i}'];
        x = df_coreg[f'{xname}{i}']
        y = df_coreg[f'{yname}{i}'];
        #y=df_coreg[f'wTF_Disp_{i}'] + fsl_shift   #identic

        ax.scatter(x,y);ax.plot([x.min(),x.max()],[x.min(),x.max()]);
        #ax.hist(y-x, bins=64);
        max_error = np.max(np.abs(y-x)); mean_error = np.mean(np.abs(y-x))
        max_errors = max_error if max_error>max_errors else max_errors
        corrPs, Pval = ss.pearsonr(x, y)
        print(f'cor is {corrPs} P {Pval} max error for {i} is {max_error}')
        ax.title.set_text(f'R = {corrPs:.2f} err mean {mean_error:.2f} max {max_error:.2f}')
    fig.text(0.5, 0.04, xname, ha='center')
    fig.text(0.04, 0.5, yname, va='center', rotation='vertical')
    print(f'Yname {yname} max  is {max_errors}')
    # m_wTF_Disp_ +fsl_shift ==  before_coreg_wTF_Disp_

plt.figure();plt.scatter(df_coreg.w_exp_shaw_disp5, df_coreg.w_quat_shaw_disp5)
err = df_coreg.w_exp_shaw_disp5 - df_coreg.w_quat_shaw_disp5
df_coreg.fp.Valeus[err.argmax()]
wshift_quat, wshift_exp, lin_fitpar = average_fitpar(fitpar)


#plot sigmas
ykeys=['m_grad_H_camb','m_grad_H_nL2','m_grad_H_corr','m_grad_H_dice','m_grad_H_kl','m_grad_H_jensen','m_grad_H_topsoe','m_grad_H_inter']
for k in ykeys:
    print(np.sum(np.isnan(df_coreg[k].values)))

ykeys=['error_w_exp_TF_rot', 'error_w_exp_shaw_rot', 'error_w2_exp_TF_rot', 'error_w2_exp_shaw_rot', 'error_zero_shift_rot', 'error_mean_shift_rot']
ykeys=['stra','m_L1_map', 'm_NCC', 'm_ssim_SSIM', 'm_grad_ratio', 'm_nRMSE', 'm_grad_nMI2', 'm_grad_EGratio','m_grad_cor_diff_ratio']
ykeys=['stra','m_L1_map', 'm_NCC', 'm_ssim_SSIM', 'm_grad_ratio', 'm_nRMSE', 'm_grad_nMI2', 'm_grad_EGratio','m_grad_cor_diff_ratio']
ykeys_noshift = ['no_shift_'+ kk[2:] for kk in ykeys]
cmap = sns.color_palette("coolwarm", len(df_coreg.amplitude.unique()))
ykey = 'm_NCC_brain' #ykeys_noshift[0]
for ykey in ykeys:
    fig = sns.relplot(data=df_coreg, x="sigma", y=ykey, hue="amplitude", legend='full', kind="line",
                  palette=cmap, col='mvt_type', col_wrap=2)

#different sigma
dfsub = df_coreg[df_coreg['sym']==1]
dfsub = df_coreg[df_coreg['no_shift']==0]

#dfsub = df_coreg[(df_coreg['sym']==0) & (df_coreg['no_shift']==0)]
cmap = sns.color_palette("coolwarm", len(df_coreg.sigma.unique()))
for ykey in ykeys:
    fig = sns.relplot(data=dfsub, x="xend", y=ykey, hue="sigma", legend='full', kind="line",
                  palette=cmap, col='amplitude', col_wrap=2, style='mvt_axe') #, style='no_shift')
    for ax in fig.axes: ax.grid()


#plot_volume index x0 for different sigma
sigmas = [2, 4,  8,  16,  32, 64, 128] #np.linspace(2,256,128).astype(int), # [2, 4,  8,  16,  32, 44, 64, 88, 128], ,
x0_min, nb_x0s = 0, 32
resolution, sym = 512, False
plt.figure();plt.grid()
for sigma in sigmas:
    if sym:
        xcenter = resolution // 2 #- sigma // 2;
        # x0s = np.floor(np.linspace(xcenter - x0_min, xcenter, nb_x0s))
        x0s = np.floor(np.linspace(x0_min, xcenter, nb_x0s))
        x0s = x0s[x0s >= sigma // 2]  # remove first point to not reduce sigma
        x0s = x0s[x0s <= (xcenter - sigma // 2)]  # remove last points to not reduce sigma because of sym
    else:
        xcenter = resolution // 2;
        x0s = np.floor(np.linspace(x0_min, xcenter, nb_x0s))
        x0s = x0s[x0s >= sigma // 2]  # remove first point to not reduce sigma
    plt.plot(np.array(x0s), range(len(x0s)))
    print(f'sigma  {sigma} nb_x {len(x0s)}')
    print(x0s)
plt.legend(sigmas)


# expand no_shift column to lines
col_no_shift, new_col_name = [], [];
col_map = dict()
for k in df1.keys():
    if 'no_shift' in k:
        col_no_shift.append(k)
        newc = 'm_' +  k[9:]
        if newc not in df1:
            newc = k[9:]
            if newc not in df1:
                print(f'error with {newc}')
        new_col_name.append(newc)
        col_map[k] = newc

dfsub2 = df1.copy() # df1[col_no_shift].copy()
dfsub1 = df1.copy()
dfsub1=dfsub1.drop(col_no_shift,axis=1)
dfsub2=dfsub2.drop(new_col_name,axis=1)
dfsub2 = dfsub2.rename(columns = col_map)
dfsub1.loc[:,'no_shift'] = 0; dfsub2.loc[:,'no_shift'] = 1;
df_coreg = pd.concat([dfsub1, dfsub2], axis=0, sort=True)
df_coreg.index = range(len(df_coreg))





def get_sujname_output_from_sigma_params(df, out_path, filename):
    for i, row in df.iterrows():
        suj_name = f'Suj_{row["subject_name"]}_I{int(row["suj_index"])}_C{int(row["suj_contrast"])}_N_{int(row["suj_noise"] * 100)}_D{int(row["suj_deform"]):d}_S{int(row["suj_seed"])}'
        amplitude_str = f'{row["amplitude"]}'
        extend=False
        if len(amplitude_str)>2:
            amplitude_str =amplitude_str[:-2] + '*'
            extend=True
        mvt_type = row["mvt_type"] if row['sym'] is False else 'Ustep' #arg todo correct right name in generation
        fp_name  = f'fp_x{int(row["x0"])}_sig{int(row["sigma"])}_Amp{amplitude_str}_M{mvt_type}_A{row["mvt_axe"]}_sym{int(row["sym"])}'
        suj_name += fp_name
        out_dir =  out_path + '/' + suj_name + '/' + filename
        if extend:
            oo = glob.glob(out_dir)
            if len(oo)!=1:
                print(f'ERROR  four {len(oo)} for {out_dir}')
            else:
                out_dir = oo[0]
        df.loc[i,'out_dir'] = out_dir
    return df

df1 = get_sujname_output_from_sigma_params(df1,out_path,'vol_motion_no_shift.nii')
mv_ax='rotY'
dfsub = df1[df1['mvt_axe'] == mv_ax]

amp_val = np.sort(dfsub.amplitude.unique())
#write output 4D for center x0
for mv_ax in df1['mvt_axe'].unique():
    dfsub = df1[df1['mvt_axe'] == mv_ax]
    amp_val = np.sort(dfsub.amplitude.unique())
    sym = 1
    for ii, amp in enumerate(amp_val):
        dd = dfsub[dfsub['amplitude']==amp]
        ddd = dd.sort_values(axis=0,by="sigma")
        out_volume = f'out_put_noshift{mv_ax}_{int(amp*100)}_sym{sym}.nii'
        print(f'writing {out_volume}')
        cmd = f'fslmerge -t {out_path}/{out_volume} '
        for vv in ddd['out_dir']:
            cmd += vv + ' '
        cmd = cmd[:-1]
        outvalue = subprocess.run(cmd.split(' '))


#write output 4D for varying x0
amp_val = np.sort(dfsub.amplitude.unique())
for mv_ax in df1['mvt_axe'].unique():
    dfsub = df1[df1['mvt_axe'] == mv_ax]
    amp_val = np.sort(dfsub.amplitude.unique())
    sym=1
    for ii, amp in enumerate(amp_val):
        dfsub_sig = dfsub[dfsub['amplitude']==amp]
        sigmas = np.sort(dfsub_sig.sigma.unique())
        for sig in sigmas:
            dd = dfsub_sig[dfsub_sig['sigma']==sig]
            ddd = dd.sort_values(axis=0,by="x0")
            #out_volume = f'out_put_noshift{mv_ax}_S{sig}_A{int(amp*100)}_sym{sym}.nii.nii'
            out_volume = f'out_put_fitpar_{mv_ax}_S{sig}_A{int(amp*100)}_sym{sym}.nii.nii'
            print(f'writing {out_volume}')
            cmd = f'fslmerge -t {out_path}/{out_volume} '
            for vv in ddd['out_dir']:
                cmd += vv + '/vol_motion.nii '
                #cmd += vv + '/vol_motion_no_shift.nii '
            cmd = cmd[:-1]
            outvalue = subprocess.run(cmd.split(' '))



one_df, smot = perform_one_motion(fp_path, fjson, fsl_coreg=False, return_motion=True)
tma = smot.history[2]

mres = ModelCSVResults(df_data=one_df, out_tmp="/tmp/rrr")
keys_unpack = ['transforms_metrics', 'm_t1'];
suffix = ['m', 'm_t1']
one_df1 = mres.normalize_dict_to_df(keys_unpack, suffix=suffix);
one_df1.m_wTF_Disp_1



#screw motion
json_file='/data/romain/PVsynth/motion_on_synth_data/test1/main.json'
df=pd.DataFrame()
param = {'amplitude': 8, 'sigma': 128, 'nb_x0s': 1, 'x0_min': 206, 'sym': False, 'mvt_type': 'Ustep',
 'mvt_axe': [6], 'cor_disp': False, 'disp_str': 'no_shift', 'suj_index': 0, 'suj_seed': 1, 'suj_contrast': 1,
 'suj_deform': False, 'suj_noise' : 0.01}
pp = SimpleNamespace(**param)

amplitude, sigma, sym, mvt_type, mvt_axe, cor_disp, disp_str, nb_x0s, x0_min =  pp.amplitude, pp.sigma, pp.sym, pp.mvt_type, pp.mvt_axe, pp.cor_disp, pp.disp_str, pp.nb_x0s, pp.x0_min
resolution, sigma, x0 = 218, int(sigma), 109
extra_info = param;
fp = corrupt_data(x0, sigma=sigma, method=mvt_type, amplitude=amplitude, mvt_axes=mvt_axe,center='none', return_all6=True, sym=sym, resolution=resolution)
testm = spm_matrix(np.hstack([fp[:,100],[1,1,1,0,0,0]]),order=0)

dq = DualQuaternion.from_homogeneous_matrix(testm)
orig_pos = [0, -80, 0] #np.array([90, 28, 90]) - np.array([90,108, 90])
#l=[1,0,0]; m = np.cross(l,orig_pos); theta = np.deg2rad(2); disp=0;
l=[0,0,1]; m = np.cross(orig_pos,l); theta = np.deg2rad(8); disp=0;  #bad this inverse origin
dq = DualQuaternion.from_screw(l, m, theta, disp)
fitpar =  np.tile(spm_imatrix(dq.homogeneous_matrix(), order=0)[:6,np.newaxis],(1,218))
cor_disp=True
smot8, df, res_fitpar, res = apply_motion(sdata, tmot, fitpar, config_runner,suj_name='rotfront_Z_2',
                                          root_out_dir='/home/romain.valabregue/tmp', param=param)