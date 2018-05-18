import sys
import matplotlib
matplotlib.use('agg')
from matplotlib import style

import cloudside

style.use('classic')

if '--strict' in sys.argv:
    sys.argv.remove('--strict')
    status = cloudside.teststrict(*sys.argv[1:])
else:
    status = cloudside.test(*sys.argv[1:])

sys.exit(status)
