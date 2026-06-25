package rca.autenticacion.api_autenticacion.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import rca.autenticacion.api_autenticacion.models.UserEntity;
import java.util.Optional;


public interface UserRepository extends JpaRepository<UserEntity, Long>{

    Optional<UserEntity> findByUsername(String username);
}
