import torch
import numpy as np
import sys
sys.path.append("../emd")
import emd_module as emd

class PointcloudToTensor(object):
    def __call__(self, points):
        return torch.from_numpy(points).float()


def angle_axis(angle: float, axis: np.ndarray):
    r"""Returns a 4x4 rotation matrix that performs a rotation around axis by angle
    Parameters
    ----------
    angle : float
        Angle to rotate by
    axis: np.ndarray
        Axis to rotate about
    Returns
    -------
    torch.Tensor
        3x3 rotation matrix
    """
    u = axis / np.linalg.norm(axis)
    cosval, sinval = np.cos(angle), np.sin(angle)

    # yapf: disable
    cross_prod_mat = np.array([[0.0, -u[2], u[1]],
                               [u[2], 0.0, -u[0]],
                               [-u[1], u[0], 0.0]])

    R = torch.from_numpy(
        cosval * np.eye(3)
        + sinval * cross_prod_mat
        + (1.0 - cosval) * np.outer(u, u)
    )
    # yapf: enable
    return R.float()


class PointcloudRotatebyAngle(object):
    def __init__(self, rotation_angle=0.0):
        self.rotation_angle = rotation_angle

    def __call__(self, pc, rotation_angle):
        self.rotation_angle = rotation_angle
        normals = pc.size(2) > 3
        bsize = pc.size()[0]
        for i in range(bsize):
            cosval = np.cos(self.rotation_angle)
            sinval = np.sin(self.rotation_angle)
            rotation_matrix = np.array([[cosval, 0, sinval],
                                        [0, 1, 0],
                                        [-sinval, 0, cosval]])
            rotation_matrix = torch.from_numpy(rotation_matrix).float().cuda()

            cur_pc = pc[i, :, :]
            if not normals:
                cur_pc = cur_pc @ rotation_matrix
            else:
                pc_xyz = cur_pc[:, 0:3]
                pc_normals = cur_pc[:, 3:]
                cur_pc[:, 0:3] = pc_xyz @ rotation_matrix
                cur_pc[:, 3:] = pc_normals @ rotation_matrix

            pc[i, :, :] = cur_pc

        return pc


class PointcloudJitter_batch(object):
    def __init__(self, std=0.01, clip=0.05):
        self.std, self.clip = std, clip

    def __call__(self, pc):
        bsize = pc.size()[0]
        for i in range(bsize):
            jittered_data = pc.new(pc.size(1), 3).normal_(
                mean=0.0, std=self.std
            ).clamp_(-self.clip, self.clip)
            pc[i, :, 0:3] += jittered_data

        return pc


class PointcloudJitter(object):
    def __init__(self, std=0.01, clip=0.05):
        self.std, self.clip = std, clip

    def __call__(self, points):
        jittered_data = (
            points.new(points.size(0), 3)
                .normal_(mean=0.0, std=self.std)
                .clamp_(-self.clip, self.clip)
        )
        points[:, 0:3] += jittered_data
        return points


class PointcloudScaleAndTranslate(object):
    def __init__(self, scale_low=2. / 3., scale_high=3. / 2., translate_range=0.2):
        self.scale_low = scale_low
        self.scale_high = scale_high
        self.translate_range = translate_range

    def __call__(self, pc):
        bsize = pc.size()[0]
        dim = pc.size()[-1]

        for i in range(bsize):
            xyz1 = np.random.uniform(low=self.scale_low, high=self.scale_high, size=[dim])
            xyz2 = np.random.uniform(low=-self.translate_range, high=self.translate_range, size=[dim])

            pc[i, :, 0:3] = torch.mul(pc[i, :, 0:3], torch.from_numpy(xyz1).float().cuda()) + torch.from_numpy(
                xyz2).float().cuda()

        return pc


class PointcloudScaleAndTranslate2(object):
    def __init__(self, scale_low=2. / 3., scale_high=3. / 2., translate_range=0.05):
        self.scale_low = scale_low
        self.scale_high = scale_high
        self.translate_range = translate_range

    def __call__(self, pc):
        bsize = pc.size()[0]
        dim = pc.size()[-1]

        for i in range(bsize):
            xyz1 = np.random.uniform(low=self.scale_low, high=self.scale_high, size=[dim])
            xyz2 = np.random.uniform(low=-self.translate_range, high=self.translate_range, size=[dim])

            pc[i, :, 0:2] = torch.mul(pc[i, :, 0:2], torch.from_numpy(xyz1).float().cuda()) + torch.from_numpy(
                xyz2).float().cuda()

        return pc


class PointcloudScale_batch(object):
    def __init__(self, scale_low=2. / 3., scale_high=3. / 2.):
        self.scale_low = scale_low
        self.scale_high = scale_high

    def __call__(self, pc):
        bsize = pc.size()[0]
        for i in range(bsize):
            xyz1 = np.random.uniform(low=self.scale_low, high=self.scale_high, size=[3])

            pc[i, :, 0:3] = torch.mul(pc[i, :, 0:3], torch.from_numpy(xyz1).float().cuda())

        return pc


class PointcloudScale(object):
    def __init__(self, lo=0.8, hi=1.25):
        self.lo, self.hi = lo, hi

    def __call__(self, points):
        scaler = np.random.uniform(self.lo, self.hi)
        points[:, 0:3] *= scaler
        return points


class PointcloudTranslate_batch(object):
    def __init__(self, translate_range=0.2):
        self.translate_range = translate_range

    def __call__(self, pc):
        bsize = pc.size()[0]
        for i in range(bsize):
            xyz2 = np.random.uniform(low=-self.translate_range, high=self.translate_range, size=[3])

            pc[i, :, 0:3] = pc[i, :, 0:3] + torch.from_numpy(xyz2).float().cuda()

        return pc


class PointcloudTranslate(object):
    def __init__(self, translate_range=0.1):
        self.translate_range = translate_range

    def __call__(self, points):
        translation = np.random.uniform(-self.translate_range, self.translate_range)
        points[:, 0:3] += translation
        return points


class PointcloudRotate(object):
    def __init__(self, axis=np.array([0.0, 1.0, 0.0])):
        self.axis = axis

    def __call__(self, points):
        rotation_angle = np.random.uniform() * 2 * np.pi
        rotation_matrix = angle_axis(rotation_angle, self.axis)

        normals = points.size(1) > 3
        if not normals:
            return torch.matmul(points, rotation_matrix.t())
        else:
            pc_xyz = points[:, 0:3]
            pc_normals = points[:, 3:]
            points[:, 0:3] = torch.matmul(pc_xyz, rotation_matrix.t())
            points[:, 3:] = torch.matmul(pc_normals, rotation_matrix.t())

            return points


class PointcloudRotatePerturbation(object):
    def __init__(self, angle_sigma=0.06, angle_clip=0.18):
        self.angle_sigma, self.angle_clip = angle_sigma, angle_clip

    def _get_angles(self):
        angles = np.clip(
            self.angle_sigma * np.random.randn(3), -self.angle_clip, self.angle_clip
        )

        return angles

    def __call__(self, points):
        angles = self._get_angles()
        Rx = angle_axis(angles[0], np.array([1.0, 0.0, 0.0]))
        Ry = angle_axis(angles[1], np.array([0.0, 1.0, 0.0]))
        Rz = angle_axis(angles[2], np.array([0.0, 0.0, 1.0]))

        rotation_matrix = torch.matmul(torch.matmul(Rz, Ry), Rx)

        normals = points.size(1) > 3
        if not normals:
            return torch.matmul(points, rotation_matrix.t())
        else:
            pc_xyz = points[:, 0:3]
            pc_normals = points[:, 3:]
            points[:, 0:3] = torch.matmul(pc_xyz, rotation_matrix.t())
            points[:, 3:] = torch.matmul(pc_normals, rotation_matrix.t())

            return points


class PointcloudRotatePerturbation_batch(object):
    def __init__(self, angle_sigma=0.06, angle_clip=0.18):
        self.angle_sigma, self.angle_clip = angle_sigma, angle_clip

    def _get_angles(self):
        angles = np.clip(
            self.angle_sigma * np.random.randn(3), -self.angle_clip, self.angle_clip
        )
        # angles = np.random.uniform(size=3) * 2 * np.pi

        return angles

    def __call__(self, points):
        bsize = points.size()[0]
        for i in range(bsize):
            angles = self._get_angles()
            Rx = angle_axis(angles[0], np.array([1.0, 0.0, 0.0]))
            Ry = angle_axis(angles[1], np.array([0.0, 1.0, 0.0]))
            Rz = angle_axis(angles[2], np.array([0.0, 0.0, 1.0]))

            rotation_matrix = torch.matmul(torch.matmul(Rz, Ry), Rx).cuda()

            normals = points.size(2) > 3
            if not normals:
                points[i, :, 0:3] = torch.matmul(points[i, :, 0:3], rotation_matrix.t())

            else:
                pc_xyz = points[i, :, 0:3]
                pc_normals = points[i, :, 3:]
                points[i, :, 0:3] = torch.matmul(pc_xyz, rotation_matrix.t())
                points[i, :, 3:] = torch.matmul(pc_normals, rotation_matrix.t())

            return points


class PointcloudRandomInputDropout_batch(object):
    def __init__(self, max_dropout_ratio=0.875):
        assert max_dropout_ratio >= 0 and max_dropout_ratio < 1
        self.max_dropout_ratio = max_dropout_ratio

    def __call__(self, pc):
        bsize = pc.size()[0]
        for i in range(bsize):
            dropout_ratio = np.random.random() * self.max_dropout_ratio  # 0~0.875
            drop_idx = np.where(np.random.random((pc.size()[1])) <= dropout_ratio)[0]
            if len(drop_idx) > 0:
                cur_pc = pc[i, :, :]
                cur_pc[drop_idx.tolist(), 0:3] = cur_pc[0, 0:3].repeat(len(drop_idx), 1)  # set to the first point
                pc[i, :, :] = cur_pc

        return pc


class PointcloudRandomInputDropout(object):
    def __init__(self, max_dropout_ratio=0.875):
        assert max_dropout_ratio >= 0 and max_dropout_ratio < 1
        self.max_dropout_ratio = max_dropout_ratio

    def __call__(self, pc):
        # pc = points.numpy()

        dropout_ratio = np.random.random() * self.max_dropout_ratio  # 0~0.875
        drop_idx = np.where(np.random.random((pc.shape[0])) <= dropout_ratio)[0]
        if len(drop_idx) > 0:
            pc[drop_idx] = pc[0]  # set to the first point

        return pc  # torch.from_numpy(pc).float()

def augmix(data, beta=1.0, n_sample=1024, lam_t = 0.5, lam_o=0.2) :
  transforms_a = [
      PointcloudRotatePerturbation_batch(),
      PointcloudTranslate_batch(),
      PointcloudJitter_batch()
    ]
  
  transforms_b = [
      PointcloudScale_batch(),
      PointcloudTranslate_batch(),
      PointcloudJitter_batch()
    ]

  data_a = data.detach()
  data_b = data.detach()
  data_o = data.detach()

  for f in transforms_a :
    data_a = f(data_a)
  
  for f in transforms_b :
    data_b = f(data_b)

  temd = emd.emdModule().cuda()

  dis, ass = temd(data_a, data_b, 0.005, 300)
  
  for i in range(data.shape[0]) :
    data_b[i] = data_b[i][ass[i].long()]

  data_t = data_a * lam_t + data_b * (1 - lam_t)

  dis, ass = temd(data_o, data_t, 0.005, 300)

  for i in range(data.shape[0]) :
    data_t[i] = data_t[i][ass[i].long()]
  data_r = data_o * lam_o + data_t * (1 - lam_o)

  return data_r

def augmix_cutmix(data, batch_size = 32, beta=1.0, n_sample=1024, lam_r = 0.5, lam_s = 0.5, rotate_clip = 1.0, scale_low = 2. / 3., scale_high = 3. / 2., jitter_clip = 0.05) :
  transforms_a = [
      PointcloudRotatePerturbation_batch(angle_clip=rotate_clip),
      PointcloudTranslate_batch(),
      PointcloudJitter_batch(clip = jitter_clip)
    ]
  
  transforms_b = [
      PointcloudScale_batch(scale_low = scale_low, scale_high = scale_high),
      PointcloudTranslate_batch(),
      PointcloudJitter_batch(clip = jitter_clip)
    ]

  data_a = data.detach()
  data_b = data.detach()

  for f in transforms_a :
    data_a = f(data_a)
  
  for f in transforms_b :
    data_b = f(data_b)

  temd = emd.emdModule().cuda()

  dis_a, ass_a = temd(data, data_a, 0.005, 300)
  dis_b, ass_b = temd(data, data_b, 0.005, 300)
  
  for i in range(data.shape[0]) :
    data_a[i] = data_a[i][ass_a[i].long()]
    data_b[i] = data_b[i][ass_b[i].long()]

  random_point_a, random_point_b = torch.split(torch.from_numpy(np.random.choice(1024, batch_size*2, replace=False, p=None)), batch_size)
  # kNN
  batch_idxs = torch.tensor(range(batch_size))
  query = data[batch_idxs, random_point_a].view(batch_size, 1, 3)
  dist = torch.sqrt(torch.sum((data - query.repeat(1, n_sample, 1)) ** 2, 2))
  idxs = dist.topk(int(n_sample*lam_r), dim=1, largest=False, sorted=True).indices
  for i in range(batch_size):
    data[i, idxs[i], :] = data_a[i, idxs[i], :]

  query = data[batch_idxs, random_point_b].view(batch_size, 1, 3)
  dist = torch.sqrt(torch.sum((data - query.repeat(1, n_sample, 1)) ** 2, 2))
  idxs = dist.topk(int(n_sample*lam_s), dim=1, largest=False, sorted=True).indices
  for i in range(batch_size):
    data[i, idxs[i], :] = data_b[i, idxs[i], :]

  return data

def augmix_cutmix_ver(data, batch_size = 32, beta=1.0, n_sample=1024, lam_a = 0.5, lam_b = 0.5, rotate_clip_a = 1.0, rotate_clip_b = 1.0, jitter_clip = 0.05) :
  transforms_a = [
      PointcloudRotatePerturbation_batch(angle_clip=rotate_clip_a),
      PointcloudTranslate_batch(),
      PointcloudJitter_batch(clip = jitter_clip)
    ]
  
  transforms_b = [
      PointcloudRotatePerturbation_batch(angle_clip=rotate_clip_b),
      PointcloudTranslate_batch(),
      PointcloudJitter_batch(clip = jitter_clip)
    ]

  data_a = data.detach()
  data_b = data.detach()

  for f in transforms_a :
    data_a = f(data_a)
  
  for f in transforms_b :
    data_b = f(data_b)

  temd = emd.emdModule().cuda()

  dis_a, ass_a = temd(data, data_a, 0.005, 300)
  dis_b, ass_b = temd(data, data_b, 0.005, 300)
  
  for i in range(data.shape[0]) :
    data_a[i] = data_a[i][ass_a[i].long()]
    data_b[i] = data_b[i][ass_b[i].long()]

  random_point_a, random_point_b = torch.split(torch.from_numpy(np.random.choice(1024, batch_size*2, replace=False, p=None)), batch_size)
  # kNN
  batch_idxs = torch.tensor(range(batch_size))
  query = data[batch_idxs, random_point_a].view(batch_size, 1, 3)
  dist = torch.sqrt(torch.sum((data - query.repeat(1, n_sample, 1)) ** 2, 2))
  idxs = dist.topk(int(n_sample*lam_a), dim=1, largest=False, sorted=True).indices
  for i in range(batch_size):
    data[i, idxs[i], :] = data_a[i, idxs[i], :]

  query = data[batch_idxs, random_point_b].view(batch_size, 1, 3)
  dist = torch.sqrt(torch.sum((data - query.repeat(1, n_sample, 1)) ** 2, 2))
  idxs = dist.topk(int(n_sample*lam_b), dim=1, largest=False, sorted=True).indices
  for i in range(batch_size):
    data[i, idxs[i], :] = data_b[i, idxs[i], :]

  return data