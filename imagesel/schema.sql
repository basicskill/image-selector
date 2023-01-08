-- Create a table for storing admins
DROP TABLE IF EXISTS admins;

CREATE TABLE admins (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password TEXT UNIQUE NOT NULL,
  img_classes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- Create a table for storing the workers
DROP TABLE IF EXISTS workers;

CREATE TABLE workers (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  token TEXT UNIQUE NOT NULL,
  eligible_classes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create a table for storing the images
DROP TABLE IF EXISTS images;

CREATE TABLE images (
  id SERIAL PRIMARY KEY,
  filename TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processing TEXT NOT NULL DEFAULT 'unprocessed',
  class_count INTEGER NOT NULL DEFAULT 0,
  classification TEXT  NOT NULL DEFAULT 'non'
);

-- Create logs table with id, textmsg and timestamp
DROP TABLE IF EXISTS logs;

CREATE TABLE logs (
  id SERIAL PRIMARY KEY,
  textmsg TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO admins (username, password) VALUES ('admin', 'pbkdf2:sha256:260000$cmrM38xFLW1PNTw5$88fa1f8f6510dc1f0e5ede3f79a5daeb04a65e1bed5d35aab8b88f549cba6343');