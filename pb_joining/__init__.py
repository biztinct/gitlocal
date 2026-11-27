from . import models, controllers


def post_init_hook(env):
    env['pb.hiring.message.template']._joining_seed()
