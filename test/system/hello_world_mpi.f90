program hello_world_mpi
  use mpi
  integer size, rank, ierr
  call MPI_INIT(ierr)
  call MPI_COMM_SIZE(MPI_COMM_WORLD, size, ierr)
  call MPI_COMM_RANK(MPI_COMM_WORLD, rank, ierr)
  if (rank .eq. 0) write(*,'(I6,A,I1,A)') size, '.', rank, ': hello world'
  call MPI_FINALIZE(ierr)
end program hello_world_mpi
