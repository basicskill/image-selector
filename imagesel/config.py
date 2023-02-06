# Secret key for session
SECRET_KEY = 'dev'

# Number of correct images to show in testing phase
NUM_TEST_CORRECT = 8

# Number of incorrect images to show in testing phase
NUM_TEST_INCORRECT = 0

# Number of images from holding to show in testing phase
NUM_TEST_HOLDING = 2

# Number of images to show in labeling phase
NUM_LABELING = 10

# Number of votes to move image from holding to processed
NUM_VOTES = 3

# Number of days for deleting of logs
LOG_DELETE_PERIOD = 7

# Number of days for deleting of bans
BAN_DELETE_PERIOD = 14

# Define image states
STATES = ['processed', 'unprocessed', 'holding']

# Number of images shown per page in admin panel
PAGE_SIZE = 10
