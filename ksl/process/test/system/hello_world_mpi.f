      program hello_world_mpi
      include 'mpif.h'
      integer rank, size, ierror, tag, status(MPI_STATUS_SIZE)
      call MPI_INIT(ierror)
      call MPI_COMM_SIZE(MPI_COMM_WORLD, size, ierror)
      call MPI_COMM_RANK(MPI_COMM_WORLD, rank, ierror)
      if (rank .eq. 0) then
         write(*,'(I6,A,I1,A)') size, '.', rank, ': hello world'
      end if
      call MPI_FINALIZE(ierror)
      
      end program hello_world_mpi
      
