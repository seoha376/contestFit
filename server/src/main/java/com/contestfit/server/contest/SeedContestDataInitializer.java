package com.contestfit.server.contest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

@Component
public class SeedContestDataInitializer implements ApplicationRunner {
    private final ContestRepository contestRepository;
    private final ObjectMapper objectMapper;

    public SeedContestDataInitializer(ContestRepository contestRepository, ObjectMapper objectMapper) {
        this.contestRepository = contestRepository;
        this.objectMapper = objectMapper;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) throws IOException {
        if (contestRepository.count() > 0) {
            return;
        }

        ClassPathResource resource = new ClassPathResource("seed-data/seed.json");
        try (InputStream stream = resource.getInputStream()) {
            JsonNode contests = objectMapper.readTree(stream).path("contests");
            if (!contests.isArray()) {
                throw new IllegalStateException("seed.json에 contests 배열이 없습니다.");
            }

            List<Contest> entities = new ArrayList<>();
            for (JsonNode contest : contests) {
                String title = requiredText(contest, "title");
                String sourceUrl = requiredText(contest, "source_url");
                entities.add(new Contest(
                        title,
                        null,
                        null,
                        sourceUrl,
                        ValidationStatus.DRAFT,
                        objectMapper.writeValueAsString(contest)
                ));
            }
            contestRepository.saveAll(entities);
        }
    }

    private String requiredText(JsonNode contest, String field) {
        String value = contest.path(field).asText();
        if (value.isBlank()) {
            throw new IllegalStateException("seed.json 공모전에 " + field + " 값이 없습니다.");
        }
        return value;
    }
}
