import os
import sys
sys.path.insert(0, os.getcwd())
print os.getcwd()
sys.path.insert(0, os.path.join(os.getcwd(), os.pardir))
print os.path.join(os.getcwd(), os.pardir)
from settings import *