
-- Create img_class type
DO $$ BEGIN
    CREATE TYPE img_class AS ENUM ('unprocessed', 'holding', 'processed');
    EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create voting type
DO $$ BEGIN
    CREATE TYPE voting AS ENUM ('C1', 'C2', 'C3', 'C4', 'C5', 'non');
    EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create a table for storing the tokens
DROP TABLE IF EXISTS tokens;

CREATE TABLE tokens (
  id SERIAL PRIMARY KEY,
  token TEXT UNIQUE NOT NULL,
  passhash TEXT UNIQUE NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  inprogress BOOLEAN NOT NULL DEFAULT FALSE,
  labeling BOOLEAN NOT NULL DEFAULT FALSE,
  selected_class voting NOT NULL DEFAULT 'non'
);

-- Create a table for storing the images
DROP TABLE IF EXISTS images;

CREATE TABLE images (
  id SERIAL PRIMARY KEY,
  filename TEXT NOT NULL,
  blob BYTEA NOT NULL,
  base64_enc TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processing img_class  NOT NULL DEFAULT 'unprocessed',
  class_count INTEGER NOT NULL DEFAULT 0,
  classification voting  NOT NULL DEFAULT 'non'
);

-- Create logs table with id, textmsg and timestamp
DROP TABLE IF EXISTS logs;

CREATE TABLE logs (
  id SERIAL PRIMARY KEY,
  textmsg TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tokens (token, passhash) VALUES ('admin', 'pbkdf2:sha256:260000$cmrM38xFLW1PNTw5$88fa1f8f6510dc1f0e5ede3f79a5daeb04a65e1bed5d35aab8b88f549cba6343');