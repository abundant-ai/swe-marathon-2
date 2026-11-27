/* Render two-sided triangles on the native, distorted Freiburg 2 RGB sensor grid.
   Inputs contain xyz camera coordinates. Output is optical-axis depth in meters. */
#include <math.h>
#include <stddef.h>

typedef struct { double x,y,z; } Point;
static const double near_plane = .03;
enum { width = 640, height = 480 };

static double pixel_x[width*height], pixel_y[width*height];
static double shift_x=0, shift_y=0;
/* Undo RGB distortion at every sample once. The observed maximum shift supplies
   a conservative bounding box even along long or strongly curved image edges. */
static void initialize_pixels(void) {
    for (int j=0;j<height;j++) for (int i=0;i<width;i++) {
        double xd=(i-325.1)/520.9, yd=(j-249.7)/521.0, x=xd, y=yd;
        for (int k=0;k<22;k++) {
            double r=x*x+y*y, scale=1+r*(.2312+r*(-.7849+r*.9172));
            double dx=x*scale+2*(-.0033)*x*y+(-.0001)*(r+2*x*x);
            double dy=y*scale+(-.0033)*(r+2*y*y)+2*(-.0001)*x*y;
            x+=xd-dx; y+=yd-dy;
        }
        int a=j*width+i;
        pixel_x[a]=x*520.9+325.1; pixel_y[a]=y*521.0+249.7;
        shift_x=fmax(shift_x,fabs(pixel_x[a]-i));
        shift_y=fmax(shift_y,fabs(pixel_y[a]-j));
    }
}
static void draw(Point a, Point b, Point c, double *depth, int *face, int index) {
    Point p[] = {a,b,c};
    double x[3], y[3];
    for (int i=0;i<3;i++) {
        x[i] = 520.9*p[i].x/p[i].z + 325.1;
        y[i] = 521.0*p[i].y/p[i].z + 249.7;
    }
    int left = (int)fmax(0,fmin(width,ceil(fmin(x[0],fmin(x[1],x[2]))-shift_x)));
    int right = (int)fmin(width-1,fmax(-1,floor(fmax(x[0],fmax(x[1],x[2]))+shift_x)));
    int top = (int)fmax(0,fmin(height,ceil(fmin(y[0],fmin(y[1],y[2]))-shift_y)));
    int bottom = (int)fmin(height-1,fmax(-1,floor(fmax(y[0],fmax(y[1],y[2]))+shift_y)));
    double det=(y[1]-y[2])*(x[0]-x[2])+(x[2]-x[1])*(y[0]-y[2]);
    if (fabs(det)<1e-12) return;
    for (int j=top;j<=bottom;j++) for (int i=left;i<=right;i++) {
        int at=j*width+i;
        double sx=pixel_x[at]-x[2], sy=pixel_y[at]-y[2];
        double u=((y[1]-y[2])*sx+(x[2]-x[1])*sy)/det;
        double v=((y[2]-y[0])*sx+(x[0]-x[2])*sy)/det;
        double w=1-u-v;
        if (fmin(u,fmin(v,w)) < -1e-9) continue;
        double z=1/(u/a.z+v/b.z+w/c.z);
        if (z<depth[at]) { depth[at]=z; face[at]=index; }
    }
}

void raster(const double *triangles, size_t count, double *depth, int *face) {
    if (!shift_x) initialize_pixels();
    for (size_t i=0;i<count;i++) {
        Point in[3], out[4];
        for (int j=0;j<3;j++) {
            const double *v=triangles+9*i+3*j;
            in[j]=(Point){v[0],v[1],v[2]};
        }
        int n=0;
        for (int j=0;j<3;j++) {
            Point a=in[j], b=in[(j+1)%3];
            if (a.z>=near_plane) out[n++]=a;
            if ((a.z>=near_plane)!=(b.z>=near_plane)) {
                double t=(near_plane-a.z)/(b.z-a.z);
                out[n++]=(Point){a.x+t*(b.x-a.x),a.y+t*(b.y-a.y),near_plane};
            }
        }
        for (int j=1;j+1<n;j++) draw(out[0],out[j],out[j+1],depth,face,(int)i);
    }
}
