# Secret key for session
SECRET_KEY='dev'

# Define possible classes
CLASSES = [f"C{i}" for i in range(1, 6)]

# Define states
STATES = ["unprocessed", "processed", "holding"]

# Define number of correct images to show in testing phase
NUM_CORRECT = 4

# Define number of incorrect images to show in testing phase
NUM_INCORRECT = 4

# Define number of images from holding to show in testing phase
NUM_HOLDING = 2

# Define number of correct images to label to proceed testing
NUM_CORRECT_LABEL = 4

# Define number of images to show in labeling phase
NUM_LABELING = 10

# Define number of votes to move image from holding to processed
NUM_VOTES = 3