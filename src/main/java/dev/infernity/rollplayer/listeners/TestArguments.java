package dev.infernity.rollplayer.listeners;

import dev.infernity.rollplayer.listeners.templates.SimpleCommandListener;
import net.dv8tion.jda.api.components.container.Container;
import net.dv8tion.jda.api.components.textdisplay.TextDisplay;
import net.dv8tion.jda.api.events.interaction.command.SlashCommandInteractionEvent;
import net.dv8tion.jda.api.interactions.commands.OptionType;
import net.dv8tion.jda.api.interactions.commands.build.CommandData;
import net.dv8tion.jda.api.interactions.commands.build.Commands;
import org.jetbrains.annotations.NotNull;

import java.util.List;
import java.util.Objects;

public class TestArguments extends SimpleCommandListener {
    public TestArguments() {
        super("testargs", "testargs desc");
    }

    @Override
    public List<CommandData> getCommandData(){
        return List.of(
                Commands.slash(commandName, commandDescription)
                        .addOption(OptionType.STRING, "argument", "argument desc")
        );
    }


    public void onCommandRan(@NotNull SlashCommandInteractionEvent event) {
        event.replyComponents(Container.of(
                TextDisplay.of("Provided argument: '" + Objects.requireNonNull(event.getOption("argument")).getAsString() + "'")
        )).useComponentsV2().queue();
    }
}
