# from tools.check_env import check_pypi
# check_pypi()

import time
import argparse
from datetime import datetime
import os
import sys
import logging
import logging.handlers
import yaml

sys.path.append('./tools')

from DMR import DanmakuRender, utils
from DMR.Render import Render

import requests.packages.urllib3.util.ssl_
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL'

if __name__ == '__main__':    
    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--config',default='replay.yml')
    parser.add_argument('--default_config',default='default.yml')
    parser.add_argument('--debug',action='store_true')
    parser.add_argument('--render_only',action='store_true')
    parser.add_argument('--input_dir',type=str)
    parser.add_argument('--version',type=str)
    args = parser.parse_args()
    sys.path.append('tools')

    if args.version:
        print('DanmakuRender-4 2023.1.6.')
        print('https://github.com/SmallPeaches/DanmakuRender')
        exit(0)

    with open(args.default_config,'r',encoding='utf-8') as f:
        default_config = yaml.safe_load(f)
    
    with open(args.config,'r',encoding='utf-8') as f:
        replay_config = yaml.safe_load(f)
    
    config = utils.Config(default_config,replay_config)
    
    logging.getLogger().setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) 
    console_handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s]: %(message)s"))
    
    os.makedirs('logs',exist_ok=True)
    logname = f'logs/DMR-{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = logging.handlers.TimedRotatingFileHandler(logname, when='D', interval=1, backupCount=0, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("[%(asctime)s][%(module)s][%(levelname)s]: %(message)s"))
    
    logging.getLogger().addHandler(console_handler)
    logging.getLogger().addHandler(file_handler)

    logging.debug(f'Full config: {config.config}')
    dmr = DanmakuRender(config, args.debug)

    if args.render_only:
        logging.info('正在渲染..')
        render = Render(pipe=None, debug=True, **config.render_config)
        input_dir = args.input_dir if args.input_dir else config.default_conf['downloader']['output_dir']
        render.render_only(input_dir)
        exit(0)
    
    dmr.start()
    
    try:
        while 1:
            time.sleep(60)
    except KeyboardInterrupt:
        dmr.stop()
            
    


    
