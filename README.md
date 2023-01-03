I would like a someone to build a web application with the following characteristics:

1. Create a new database with three subfolders: "unprocessed", "processed", and "holding".
2. Within each folder, create five subfolders, each corresponding to a different class of images (C1, C2 C3, C4, C5).
3. Set up a user interface for a worker to select which class of images they would like to classify and the number of images they would like to work on.
4. Randomly select eight images from the "processed" folder and two images from the "unprocessed" folder and present them to the worker as a test.
5. If the worker correctly classifies at least seven of the eight images from the "processed" folder as belonging to the class they selected, proceed to the next step. If not, inform the worker that they are not eligible to continue.
6. Move the two images that were part of the test to a "holding" folder within the class chosen by the worker during the test.
7. For workers that passed the test, present them with a set of images from the "unprocessed" and “holding” folder corresponding to the class and number of images they selected.
8. The worker’s task is to decide whether a given image belong to the class they have selected or not. For each image the worker classified add it to the "holding" folder within the class chosen by the worker.
9. Once three workers have classified a particular image in the "holding" folder, the classification is final and should be moved to the corresponding class in the "processed" folder.
10. Create a log (which self-deletes after seven days) showing the number of images each worker has worked on and the time they spent doing the classification.

The engineer would have to:

1. Choose a programming language and framework to use for the application.
2. Design the user interface and layout of the application.
3. Implement the functionality for workers to select a class of images and the number of images they want to work on.
4. Implement the test for workers to classify images and determine their eligibility to continue.
5. Implement the functionality for workers to classify images and add them to the "holding" folder.
6. Implement the functionality for the application to move images from the "holding" folder to the "processed" folder once three or more workers have classified them.
7. Implement a log to track the number of images each worker has classified and the time they spent doing so.
8. Set up a server to host the application and make it accessible online.
9. Test the application thoroughly to ensure it is functioning correctly.


1) Should the test be given to a worker only once, or once per class, or every time they want to start working?
2) What happens if one image from "holding" is first classified as let's say C1, but next two workers mark it not C1? Should it be returned to "unprocessed"?
3) Should there be any admin panel, for managing images and worker accounts?
4) How much do you care about design? I can make something that's functional and not ugly, it just won't be stunning either.
5) Why does the worker have to choose in advance how many images he wants to classify? For me it would be more intuitive to display let's say 10 images at the time, and allow him to load 10 more if he wants, and so on. But if you think it's better to choose in advance, we can go with that too.
6) I guess you'd want to display all (or 10 by 10 if we decide on that) images on one page, have a submit button at the bottom and only submit work when worker clicks submit button. What should happen if worker starts working, but doesn't submit at the end? Should the system remember his choices for images he already marked or not? Should the time he spent before leaving be counted or not?




1) Test is only given to the worker once per class


2) That is a good idea. Two negative classifications from holding should move the image back to "unprocessed."


3) Yes. It would be great to have an admin panel to add images to "unprocessed", see images in "holding." and managing worker accounts, by giving sometype of access code to each worker before they can access the application.


4) This works for me. As long as the users can see the image (which may vary in size) and the name of the person when doing the classification that would work. Some space to eventually add some text around the image (like this https://www.google.com/search?q=one+pager+fund&sxsrf=ALiCzsaAjRtZ7iDzF1WaScxe7A4K6nauRw:1671718909221&source=lnms&tbm=isch&sa=X&ved=2ahUKEwiegP6dto38AhUZMTQIHbZtCHYQ_AUoAXoECAEQAw&biw=1920&bih=937#imgrc=BLUKnHPzchUOzM&imgdii=tq0YuDuVWdHNUM) in a future iteration would be great.


5) I agree. We can do it this way.


6) This is also a great idea. I think I would want to display a maximum of 20 images. The images should move once the worker has clicked on the classification for an image. Of course if the worker changes their classification or chooses to revisit a previous classification, that should also be possible. If a worker leaves and returns, then that is a new session and we will not try to remember the worker's page.

Also, the test images in the random pull for the test has to pull from all classes in the processed folder (4 from class chosen by user and 4 from the other classes -- chosen at random) and a random 2 from the unprocessed folder. Obviously, only the 4 images from the class chosen by the user are scored to decide whether the user can proceed.