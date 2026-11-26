Work in /app/work. If observation.png is present, open it with your image viewer to inspect the visual evidence before implementing the solution.

Reconstruct the visible workspace in the handheld RGB clip as one colored triangle mesh in meters. The recording shows one of two possible workspaces. Identify it from the RGB evidence and the camera motion. Pay particular attention to the shape, thickness, exposed contours, occlusions, and relative depths of its three named objects. Reconstruct surrounding surfaces so an object can be partly hidden when the camera moves.

The contact sheet contains six 640 by 480 RGB keyframes. Read across each row and then down. The optical axes point right, down and forward. The pinhole approximation uses fx = fy = 525 pixels, cx = 319.5 and cy = 239.5. Both odometry tracks below use the same frame order. Each row gives the camera center in meters and quaternion qx, qy, qz, qw that maps that camera's coordinates into the first camera's frame. Choose the motion consistent with the scene. You may reason about intermediate views as well as the supplied views.

Write modular standalone Python defining scene() -> (vertices, triangles, colors, face_ids). Return one fixed mesh in first-frame camera coordinates. Vertices and RGB colors are N by 3; colors are in [0,255]. The triangles are M by 3 integer vertex indices, M from 1 through 20,000. The face_ids array contains one integer per triangle. Assign 0 to the surrounding environment and 1, 2, or 3 to faces belonging to the corresponding named object. These labels refer to the visible physical items, including attached features and sides. Exclude cast shadows, detached cables, and neighboring objects. If the contact sheet is unavailable, submit your best single reconstruction. Use NumPy and standard Python.

Workspace and track I
1. gray roll of adhesive tape, including its inner rim
2. white handled mug between the mouse and the telephone
3. beige landline telephone base and handset, excluding the trailing cord
0.0000 0.0000 0.0000 0.0000 0.0000 0.0000 1.0000
0.0674 0.0255 -0.0479 -0.0033 -0.0211 -0.0115 0.9997
0.1875 0.0645 -0.0758 -0.0193 -0.0569 -0.0471 0.9971
0.2974 0.1061 -0.0756 -0.0493 -0.0699 -0.0526 0.9949
0.3913 0.1510 -0.0344 -0.1012 -0.0553 -0.0562 0.9917
0.4705 0.1365 0.0505 -0.1276 -0.0546 -0.0739 0.9876

Workspace and track II
1. black game controller body and buttons
2. red square housing with a blue disc (exclude the adjacent black connector and its cable)
3. upright white printed carton marked CHUNK
-0.0000 -0.0000 0.0000 0.0000 0.0000 0.0000 1.0000
-0.1736 -0.0053 0.0289 -0.0037 0.0062 0.0402 0.9992
-0.2801 -0.0689 0.0150 0.0570 0.0447 0.1047 0.9919
-0.3304 -0.0872 -0.0083 0.0541 0.0905 0.1750 0.9789
-0.3842 -0.0885 0.0075 0.0424 0.1408 0.2300 0.9620
-0.3585 -0.1182 -0.0042 0.0605 0.1369 0.2354 0.9603


Create submission.py in the current directory. Before submitting, execute ./python smoke.py. It calls your full implementation and checks the output contract. You may run other local tests, inspect your code, and fix failures. Rerun ./python smoke.py after your final change. Leave the supplied test unchanged. Work only in this directory and report the final test result.
