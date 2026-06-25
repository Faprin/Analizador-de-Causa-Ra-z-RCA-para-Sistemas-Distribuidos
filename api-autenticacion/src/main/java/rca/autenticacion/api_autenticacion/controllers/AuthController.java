package rca.autenticacion.api_autenticacion.controllers;

import java.util.Optional;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import rca.autenticacion.api_autenticacion.models.UserEntity;
import rca.autenticacion.api_autenticacion.payload.AuthRequest;
import rca.autenticacion.api_autenticacion.payload.AuthResponse;
import rca.autenticacion.api_autenticacion.repository.UserRepository;
import rca.autenticacion.api_autenticacion.services.JwtService;

@RequiredArgsConstructor
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final JwtService jwtService;
    private final PasswordEncoder passwordEncoder;
    private final UserRepository userRepository;

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody AuthRequest request) {

        Optional<UserEntity> userOpt = userRepository.findByUsername(request.getUsername());

        if(userOpt.isPresent() && passwordEncoder.matches(request.getPassword(), userOpt.get().getPassword())) {
            UserEntity user = userOpt.get();

            String token = jwtService.generateToken(user.getUsername());

            return ResponseEntity.ok(AuthResponse.builder()
                                            .token(token)
                                            .username(user.getUsername())
                                            .build());
        }

        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("Credenciales invalidas");
    }

    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody @Valid UserEntity user) {
        
        if(userRepository.findByUsername(user.getUsername()).isPresent()) {
            return ResponseEntity
                    .status(HttpStatus.CONFLICT)
                    .body("El usuario con nombre de usuario " + user.getUsername() + " ya existe");
        }

        String hashedPassword = passwordEncoder.encode(user.getPassword());
        UserEntity newUser = UserEntity.builder()
            .username(user.getUsername())
            .password(hashedPassword)
            .fullName(user.getFullName())
            .build();

        userRepository.save(newUser);

        String token = jwtService.generateToken(newUser.getUsername());

        return ResponseEntity.status(HttpStatus.CREATED).body(AuthResponse.builder()
                                    .token(token)
                                    .username(newUser.getUsername())
                                    .build());
    }
}
