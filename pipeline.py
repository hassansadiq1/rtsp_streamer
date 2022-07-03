import sys

sys.path.append('/opt/nvidia/deepstream/deepstream/lib')
import gi
import configparser
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
import pyds


class Pipeline:
    def __init__(self):

        self._MAX_DISPLAY_LEN = 64
        self._MUXER_OUTPUT_WIDTH = 1280
        self._MUXER_OUTPUT_HEIGHT = 720
        self._GST_CAPS_FEATURES_NVMM = "memory:NVMM"
        self._MAX_ELEMENTS_IN_DISPLAY_META = 16
        self._BITRATE = 4000000
        self.ENCODER_CODEC = 'H264'

        self._PGIE_CONFIG_FILE = "./configs/pgie_config.txt"
        self._TRACKER_CONFIG_FILE = "./configs/tracker_config.txt"

        self._loop = None
        self._pipeline = self._streammux = self._sink = None
        self._pgie = self._nvosd = None
        self._nvvideoconvert1 = self._nvvideoconvert2 = None
        self._nvvideoconvert3 = self._nvvideoconvert4 = None
        self._nvtracker = None
        self._fakesink = None
        self._capsfilter1 = self._capsfilter2 = self._capsfilter3 = None
        self._tee = self._encoder1 = self._rtppay1 = self._muxer = self._filesink = None
        self._que1 = self._que2 = self._que3 = self._que4 = None
        self._encoder2 = self._rtppay2 = None

        self._bus = None
        self._bus_watch_id = None
        self._osd_src_pad = None

        self._pgie_batch_size = 1

    def createElements(self):

        self._pipeline = Gst.Pipeline()
        self._loop = GObject.MainLoop()

        # Create nvstreammux instance to form batches from one or more sources.
        self._streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")

        # Use nvinfer to infer on batched frame.
        self._pgie = Gst.ElementFactory.make("nvinfer", "primary-nvinference-engine")

        # We need to have a tracker to track the identified objects */
        self._nvtracker = Gst.ElementFactory.make("nvtracker", "tracker")

        # Use convertor to convert from NV12 to RGBA as required by nvosd */
        self._nvvideoconvert1 = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter1")
        self._nvvideoconvert2 = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter2")
        self._nvvideoconvert3 = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter3")
        self._nvvideoconvert4 = Gst.ElementFactory.make("nvvideoconvert", "nvvideo-converter4")

        # Create OSD to draw on the converted RGBA buffer */
        self._nvosd = Gst.ElementFactory.make("nvdsosd", "nv-onscreendisplay")

        self._fakesink = Gst.ElementFactory.make("fakesink", "fake-sink1")

        self._tee = Gst.ElementFactory.make("tee", "tee-1")

        # encoder elements
        if self.ENCODER_CODEC == "H264":
            print("Creating H264 Encoder \n ")
            self._encoder1 = Gst.ElementFactory.make("nvv4l2h264enc", "encoder-h264-1")
            self._rtppay1 = Gst.ElementFactory.make("rtph264pay", "rtph264-pay-1")
            self._encoder2 = Gst.ElementFactory.make("nvv4l2h264enc", "encoder-h264-2")
            self._rtppay2 = Gst.ElementFactory.make("rtph264pay", "rtph264-pay-2")
        else:
            print("Creating H265 Encoder \n ")
            self._encoder1 = Gst.ElementFactory.make("nvv4l2h265enc", "encoder-h265-1")
            self._rtppay1 = Gst.ElementFactory.make("rtph265pay", "rtph265-pay-1")
            self._encoder2 = Gst.ElementFactory.make("nvv4l2h265enc", "encoder-h265-1")
            self._rtppay2 = Gst.ElementFactory.make("rtph265pay", "rtph265-pay-1")

        # queue elements
        self._que1 = Gst.ElementFactory.make("queue", "queue-1")
        self._que2 = Gst.ElementFactory.make("queue", "queue-2")
        self._que3 = Gst.ElementFactory.make("queue", "queue-3")
        self._que4 = Gst.ElementFactory.make("queue", "queue-4")

        # capsfilter
        self._capsfilter1 = Gst.ElementFactory.make("capsfilter", "capsfilter-1")
        self._capsfilter2 = Gst.ElementFactory.make("capsfilter", "capsfilter-2")
        self._capsfilter3 = Gst.ElementFactory.make("capsfilter", "capsfilter-3")

    def Verify(self):
        if not self._pipeline or not self._streammux or not self._fakesink:
            sys.stderr.write("Initial elements could not be created. Exiting.\n")
            exit(-1)

        if (not self._pgie or not self._nvtracker  or not self._nvosd or not self._tee):
            sys.stderr.write("Pipeline elements could not be created. Exiting.\n")
            exit(-1)
        
        if not self._nvvideoconvert1 or not self._nvvideoconvert2 or not self._nvvideoconvert3 or not self._nvvideoconvert4:
            sys.stderr.write("Nvvideoconvert elements could not be created. Exiting.\n")
            exit(-1)


        if not self._encoder1 or not self._rtppay1 or not self._encoder2 or not self._rtppay2:
            sys.stderr.write("Encoder elements could not be created. Exiting.\n")
            exit(-1)

        if (not self._que1 or not self._que2 or not self._que3 or not self._que4 or
                not self._capsfilter1 or not self._capsfilter2 or not self._capsfilter3):
            sys.stderr.write("queue or capsfilter elements could not be created. Exiting.\n")
            exit(-1)

    def Configure(self):

        self._streammux.set_property("batch-size", self._pgie_batch_size)
        self._streammux.set_property("width", self._MUXER_OUTPUT_WIDTH)
        self._streammux.set_property("height", self._MUXER_OUTPUT_HEIGHT)

        self._pgie.set_property("config-file-path", self._PGIE_CONFIG_FILE)

        # I420 required for encoder
        caps1 = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=I420")
        self._capsfilter1.set_property("caps", caps1)
        caps2 = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=I420")
        self._capsfilter2.set_property("caps", caps2)

        self._encoder1.set_property('bitrate', self._BITRATE)
        self._encoder2.set_property('bitrate', self._BITRATE)

    def set_tracker_properties(self):
        # Set properties of tracker
        config = configparser.ConfigParser()
        config.read(self._TRACKER_CONFIG_FILE)
        config.sections()

        for key in config['tracker']:
            if key == 'tracker-width':
                tracker_width = config.getint('tracker', key)
                self._nvtracker.set_property('tracker-width', tracker_width)
            if key == 'tracker-height':
                tracker_height = config.getint('tracker', key)
                self._nvtracker.set_property('tracker-height', tracker_height)
            if key == 'gpu-id':
                tracker_gpu_id = config.getint('tracker', key)
                self._nvtracker.set_property('gpu_id', tracker_gpu_id)
            if key == 'll-lib-file':
                tracker_ll_lib_file = config.get('tracker', key)
                self._nvtracker.set_property('ll-lib-file', tracker_ll_lib_file)
            if key == 'll-config-file':
                tracker_ll_config_file = config.get('tracker', key)
                self._nvtracker.set_property('ll-config-file', tracker_ll_config_file)
            if key == 'enable-batch-process':
                tracker_enable_batch_process = config.getint('tracker', key)
                self._nvtracker.set_property('enable_batch_process', tracker_enable_batch_process)
            if key == 'enable-past-frame':
                tracker_enable_past_frame = config.getint('tracker', key)
                self._nvtracker.set_property('enable_past_frame', tracker_enable_past_frame)

    def ConstructPipeline(self):
        self._pipeline.add(self._streammux)
        self._pipeline.add(self._pgie)
        self._pipeline.add(self._nvtracker)
        self._pipeline.add(self._nvvideoconvert1)
        self._pipeline.add(self._nvvideoconvert2)
        self._pipeline.add(self._nvvideoconvert3)
        self._pipeline.add(self._nvosd)
        self._pipeline.add(self._capsfilter1)
        self._pipeline.add(self._encoder1)
        self._pipeline.add(self._rtppay1)
        self._pipeline.add(self._que1)
        self._pipeline.add(self._que2)
        self._pipeline.add(self._que3)
        self._pipeline.add(self._que4)
        self._pipeline.add(self._capsfilter2)
        self._pipeline.add(self._encoder2)
        self._pipeline.add(self._rtppay2)
        self._pipeline.add(self._tee)
        # self._pipeline.add(self._fakesink)

        self._streammux.link(self._que1)
        self._que1.link(self._pgie)
        self._pgie.link(self._nvtracker)
        self._nvtracker.link(self._que2)
        self._que2.link(self._nvvideoconvert1)
        self._nvvideoconvert1.link(self._nvosd)
        self._nvosd.link(self._que3)

        self._que3.link(self._nvvideoconvert2)
        self._nvvideoconvert2.link(self._capsfilter1)
        self._capsfilter1.link(self._encoder1)
        self._encoder1.link(self._rtppay1)

        self._que4.link(self._nvvideoconvert3)
        self._nvvideoconvert3.link(self._capsfilter2)
        self._capsfilter2.link(self._encoder2)
        self._encoder2.link(self._rtppay2)
        # self._rtppay2.link(self._fakesink)
