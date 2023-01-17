-- Create a table for storing admins
DROP TABLE IF EXISTS admins;

CREATE TABLE admins (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password TEXT UNIQUE NOT NULL,
  img_classes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  created TIMESTAMP NOT NULL DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP::timestamp)
);

INSERT INTO admins (username, password) VALUES ('admin', 'pbkdf2:sha256:260000$cmrM38xFLW1PNTw5$88fa1f8f6510dc1f0e5ede3f79a5daeb04a65e1bed5d35aab8b88f549cba6343');

-- Create a table for storing the workers
DROP TABLE IF EXISTS workers;

CREATE TABLE workers (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  token TEXT UNIQUE NOT NULL,
  eligible_classes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  created TIMESTAMP NOT NULL DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP::timestamp),
  num_labeled INTEGER[] NOT NULL DEFAULT ARRAY[]::INTEGER[],
  cumulative_time_spent INTEGER[] NOT NULL DEFAULT ARRAY[]::INTEGER[]
);

-- Create a table for storing the images
DROP TABLE IF EXISTS images;

CREATE TABLE images (
  id SERIAL PRIMARY KEY,
  filename TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP::timestamp),
  processing TEXT NOT NULL DEFAULT 'unprocessed',
  class_count INTEGER NOT NULL DEFAULT 0,
  labeled_by INTEGER[] NOT NULL DEFAULT ARRAY[]::INTEGER[],
  classification TEXT NOT NULL DEFAULT '/'
);

-- Create logs table with id, textmsg and timestamp
DROP TABLE IF EXISTS logs;

CREATE TABLE logs (
  id SERIAL PRIMARY KEY,
  worker_id INTEGER NOT NULL DEFAULT -1,
  textmsg TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP::timestamp)
);

-- Create banned table for storing banned classes of workers
DROP TABLE IF EXISTS banned;

CREATE TABLE banned (
  id SERIAL PRIMARY KEY,
  worker_id INTEGER NOT NULL,
  class TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP::timestamp)
);


-- Create a table for storing worker activity
DROP TABLE IF EXISTS activity;

CREATE TABLE activity (
  id SERIAL PRIMARY KEY,
  worker_id INTEGER NOT NULL,
  num_labeled INTEGER NOT NULL,
  class TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT DATE_TRUNC('second', CURRENT_TIMESTAMP::timestamp)
);