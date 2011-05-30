#include <iostream>
#include <mpi.h>

using namespace std;

int main (int argc, char *argv[])
{
  int rank, size;
  MPI_Init (&argc, &argv);
  MPI_Comm_rank (MPI_COMM_WORLD, &rank);
  MPI_Comm_size (MPI_COMM_WORLD, &size);
  if (rank==0)
    cout << size << "." << rank << ": hello world" << endl;
  MPI_Finalize();
  return 0;
} 
