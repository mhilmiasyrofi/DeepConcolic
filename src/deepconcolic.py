import argparse
import sys
import os
import cv2
from utils import *
from deepconcolic_fuzz import deepconcolic_fuzz

def deepconcolic(criterion, norm, test_object, report_args,
                 engine_args = {}, **engine_run_args):
  engine = None
  if criterion=='nc':                   ## neuron cover
    from nc import setup as nc_setup
    if norm=='linf':
      from pulp_norms import LInfPulp
      from nc_pulp import NcPulpAnalyzer
      engine = nc_setup (test_object = test_object,
                         engine_args = engine_args,
                         setup_analyzer = NcPulpAnalyzer,
                         input_metric = LInfPulp ())
    elif norm=='l0':
      from nc_l0 import NcL0Analyzer
      engine = nc_setup (test_object = test_object,
                         engine_args = engine_args,
                         setup_analyzer = NcL0Analyzer,
                         input_shape = test_object.raw_data.data[0].shape,
                         eval_batch = eval_batch_func (test_object.dnn))
    else:
      print('\n not supported norm... {0}\n'.format(norm))
      sys.exit(0)
  elif criterion=='ssc':
    from ssc import SScGANBasedAnalyzer, setup as ssc_setup
    engine = ssc_setup (test_object = test_object,
                        engine_args = engine_args,
                        setup_analyzer = SScGANBasedAnalyzer,
                        ref_data = test_object.raw_data)
  elif criterion=='ssclp':
    from pulp_norms import LInfPulp
    from mcdc_pulp import SScPulpAnalyzer
    from ssc import setup as ssc_setup
    engine = ssc_setup (test_object = test_object,
                        engine_args = engine_args,
                        setup_analyzer = SScPulpAnalyzer,
                        input_metric = LInfPulp ())
  elif criterion=='svc':
    from run_ssc import run_svc
    print('\n== Starting DeepConcolic tests for {0} =='.format (test_object))
    run_svc(test_object, report_args['outdir'].path)
  else:
    print('\n not supported coverage criterion... {0}\n'.format(criterion))
    sys.exit(0)

  if engine != None:
    engine.run (**report_args, **engine_run_args)


def main():

  parser=argparse.ArgumentParser(description='Concolic testing for neural networks' )
  parser.add_argument('--model', dest='model', default='-1',
                      help='the input neural network model (.h5)')
  parser.add_argument("--inputs", dest="inputs", default="-1",
                      help="the input test data directory", metavar="DIR")
  parser.add_argument("--outputs", dest="outputs", default="-1",
                      help="the outputput test data directory", metavar="DIR")
  parser.add_argument("--training-data", dest="training_data", default="-1",
                      help="the extra training dataset", metavar="DIR")
  parser.add_argument("--criterion", dest="criterion", default="nc",
                      help="the test criterion", metavar="nc, ssc...")
  parser.add_argument("--init", dest="init_tests", metavar="INT",
                      help="number of test samples to initialize the engine")
  parser.add_argument("--labels", dest="labels", default="-1",
                      help="the default labels", metavar="FILE")
  parser.add_argument("--mnist-dataset", dest="mnist",
                      help="MNIST dataset", action="store_true")
  parser.add_argument("--cifar10-dataset", dest="cifar10",
                      help="CIFAR-10 dataset", action="store_true")
  parser.add_argument("--vgg16-model", dest='vgg16',
                      help="vgg16 model", action="store_true")
  parser.add_argument("--norm", dest="norm", default="l0",
                      help="the norm metric", metavar="linf, l0")
  parser.add_argument("--input-rows", dest="img_rows", default="224",
                      help="input rows", metavar="INT")
  parser.add_argument("--input-cols", dest="img_cols", default="224",
                      help="input cols", metavar="INT")
  parser.add_argument("--input-channels", dest="img_channels", default="3",
                      help="input channels", metavar="INT")
  parser.add_argument("--cond-ratio", dest="cond_ratio", default="0.01",
                      help="the condition feature size parameter (0, 1]", metavar="FLOAT")
  parser.add_argument("--top-classes", dest="top_classes", default="1",
                      help="check the top-xx classifications", metavar="INT")
  parser.add_argument("--layer-index", dest="layer_indexes",
                      nargs="+", type=int,
                      help="to test a particular layer", metavar="INT")
  parser.add_argument("--feature-index", dest="feature_index", default="-1",
                      help="to test a particular feature map", metavar="INT")
  # fuzzing params
  parser.add_argument("--fuzzing", dest='fuzzing', help="to start fuzzing", action="store_true")
  parser.add_argument("--num-tests", dest="num_tests", default="1000",
                    help="number of tests to generate", metavar="INT")
  parser.add_argument("--num-processes", dest="num_processes", default="1",
                    help="number of processes to use", metavar="INT")
  parser.add_argument("--sleep-time", dest="stime", default="4",
                    help="fuzzing sleep time", metavar="INT")
  
  args=parser.parse_args()


  criterion=args.criterion
  norm=args.norm
  cond_ratio=float(args.cond_ratio)
  top_classes=int(args.top_classes)

  test_data=None
  train_data = None
  img_rows, img_cols, img_channels = int(args.img_rows), int(args.img_cols), int(args.img_channels)

  dnn = None
  inp_ub = 1
  save_input = None
  if args.fuzzing:
      pass
  elif args.model!='-1':
    dnn = keras.models.load_model (args.model)
    dnn.summary()
    save_input = save_an_image
  elif args.vgg16:
    dnn = keras.applications.VGG16 ()
    inp_ub = 255
    dnn.summary()
    save_input = save_an_image
  else:
    print (' \n == Please specify the input neural network == \n')
    sys.exit(0)

  # fuzzing_params
  if args.inputs!='-1':
    file_list = []
    xs=[]
    np1 ('Loading input data from {}... '.format (args.inputs))
    for path, subdirs, files in os.walk(args.inputs):
      for name in files:
        fname=(os.path.join(path, name))
        file_list.append(fname) # fuzzing params
        if fname.endswith('.jpg') or fname.endswith('.png'):
          try:
            image = cv2.imread(fname)
            image = cv2.resize(image, (img_rows, img_cols))
            image = image.astype('float')
            xs.append((image))
          except: pass
    x_test = np.asarray(xs)
    x_test = x_test.reshape(x_test.shape[0], img_rows, img_cols, img_channels)
    test_data = raw_datat(x_test, None)
    print (len(xs), 'loaded.')
  elif args.mnist:
    from tensorflow.keras.datasets import mnist
    print ('Loading MNIST data... ', end = '', flush = True)
    img_rows, img_cols, img_channels = 28, 28, 1
    (x_train, y_train), (x_test, y_test) = mnist.load_data()
    x_test = x_test.reshape(x_test.shape[0], img_rows, img_cols, img_channels)
    x_test = x_test.astype('float32')
    x_test /= 255
    test_data = raw_datat(x_test, y_test, 'mnist')
    x_train = x_train.reshape(x_train.shape[0], img_rows, img_cols, img_channels)
    x_train = x_train.astype('float32')
    x_train /= 255
    train_data = raw_datat(x_train, y_train, 'mnist')
    print ('done.')
  elif args.cifar10:
    from tensorflow.keras.datasets import cifar10
    print ('Loading CIFAR10 data... ', end='', flush = True)
    img_rows, img_cols, img_channels = 32, 32, 3
    (x_train, y_train), (x_test, y_test) = cifar10.load_data()
    x_test = x_test[0:3000]             # select only a few...
    x_test = x_test.reshape(x_test.shape[0], img_rows, img_cols, img_channels)
    x_test = x_test.astype('float32') / 255.
    test_data = raw_datat(x_test, y_test[0:3000], 'cifar10')
    x_train = x_train.reshape(x_train.shape[0], img_rows, img_cols, img_channels)
    x_train = x_train.astype('float32') / 255.
    train_data = raw_datat(x_train, y_train, 'cifar10')
    print ('done.')
  else:
    print (' \n == Please input dataset == \n')
    sys.exit(0)

  outs=None
  if args.outputs!='-1':
    outs=args.outputs
  else:
    print (' \n == Please specify the output directory == \n')
    sys.exit(0)

  test_object=test_objectt(dnn, test_data, train_data)
  test_object.cond_ratio = cond_ratio
  test_object.top_classes = top_classes
  test_object.inp_ub = inp_ub
  if args.layer_indexes is not None:
    try:
      test_object.layer_indices=[]
      for layer_index in tuple(args.layer_indexes):
        layer = dnn.get_layer (index = int (layer_index))
        test_object.layer_indices.append (dnn.layers.index (layer))
    except ValueError as e:
      sys.exit (e)
    if args.feature_index!='-1':
      test_object.feature_indices=[]
      test_object.feature_indices.append(int(args.feature_index))
      print ('feature index specified:', test_object.feature_indices)
  if args.training_data!='-1':          # NB: never actually used
    tdata=[]
    print ('To load the extra training data...')
    for path, subdirs, files in os.walk(args.training_data):
      for name in files:
        fname=(os.path.join(path, name))
        if fname.endswith('.jpg') or fname.endswith('.png'):
          try:
            image = cv2.imread(fname)
            image = cv2.resize(image, (img_rows, img_cols))
            image=image.astype('float')
            tdata.append((image))
          except: pass
    print ('The extra training data loaded: ', len(tdata))
    # test_object.training_data=tdata

  if args.labels!='-1':             # NB: only used in run_scc.run_svc
    labels=[]
    lines = [line.rstrip('\n') for line in open(args.labels)]
    for line in lines:
      for l in line.split():
        labels.append(int(l))
    test_object.labels=labels

  init_tests = int (args.init_tests) if args.init_tests is not None else None

  # fuzzing params
  if args.fuzzing:
    deepconcolic_fuzz(test_object, outs, args.model, int(args.stime), file_list,
                      num_tests = int(args.num_tests),
                      num_processes = int(args.num_processes))
    sys.exit(0)

  test_object.check_layer_indices (criterion)
  deepconcolic (criterion, norm, test_object,
                report_args = { 'outdir': OutputDir (outs, log = True),
                                'save_new_tests': True,
                                'save_input_func': save_input,
                                'inp_ub': inp_ub },
                initial_test_cases = init_tests,
                max_iterations = None)

if __name__=="__main__":
  try:
    main ()
  except KeyboardInterrupt:
    sys.exit('Interrupted.')
